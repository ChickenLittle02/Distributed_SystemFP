// Package origen es el nodo dueño de la versión de referencia en la fase 2.
//
// Responsabilidad: repartir los archivos de la carpeta de contenido por HTTP
// (GET /<recurso>), confirmar sin bytes que la versión local de un borde
// sigue siendo la actual (X-Version-Local → 304), aceptar la publicación
// (PUT /<recurso> crea o reemplaza, DELETE /<recurso> borra), llevar la
// versión de cada recurso (hash SHA-256 como única señal de cambio,
// persistida en <contenido>/.versiones.json) y, tras un PUT o un DELETE,
// avisar a los bordes anotados en la configuración (POST /_invalidar/…)
// con tiempo de espera. Anota responde, publica, borra, invalidar, timeout
// y nodo_caido en el historial.
// No es el borde: no hace hit/miss, TTL, STALE_LIMIT ni expulsión, y no
// toca las copias de nadie. No abre sockets: el servidor HTTP lo arranca
// cmd/origen y las llamadas a los bordes salen por el paquete transporte.
// El borde que no contesta no entra en la lista de avisados; el que
// recibe y no aplica (202) tampoco, y es él quien anota invalidacion_perdida.
package origen

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/protocolo"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/transporte"
)

// Nombre del nodo en el historial.
const Nombre = "origen"

// archivoVersiones es donde el origen persiste versión y hash por recurso,
// para que un reinicio no vuelva a la versión 1 (decisión de la fase 2).
const archivoVersiones = ".versiones.json"

// entrada es lo que el origen recuerda de un recurso.
type entrada struct {
	Version int    `json:"version"`
	Hash    string `json:"hash"`
}

// Respuesta es lo que el origen contesta a un GET, antes de ponerlo en HTTP.
type Respuesta struct {
	Existe    bool
	Misma     bool // la versión local coincidía: no viajan bytes
	Version   int
	Contenido []byte
}

// Aviso es el resultado de una invalidación: a quién llegó y qué versión.
type Aviso struct {
	Recurso  string
	Version  int // 0 si el archivo ya no está
	Existe   bool
	Avisados []string
}

// Origen es el estado del nodo. Entra (al crearlo): la configuración.
// Sale: Responder, Publicar, Borrar, Invalidar y el manejador HTTP.
// Si el otro nodo no contesta: solo llama a los bordes en Invalidar; el
// que no contesta en el plazo queda fuera de la lista y deja su línea.
type Origen struct {
	cfg        *config.Config
	dir        string
	transporte *transporte.Transporte
	mu         sync.Mutex
	versiones  map[string]entrada
}

// Nuevo crea el origen y carga las versiones persistidas si las hay.
func Nuevo(cfg *config.Config) (*Origen, error) {
	o := &Origen{
		cfg:        cfg,
		dir:        cfg.Contenido,
		transporte: transporte.Nuevo(cfg.Timeout(), cfg.Cifrado),
		versiones:  map[string]entrada{},
	}
	if err := os.MkdirAll(o.dir, 0o755); err != nil {
		return nil, err
	}
	if datos, err := os.ReadFile(filepath.Join(o.dir, archivoVersiones)); err == nil {
		_ = json.Unmarshal(datos, &o.versiones)
	}
	return o, nil
}

// Listo deja la línea de arranque, con la configuración que importa.
func (o *Origen) Listo(direccion string) {
	registro.Registrar(Nombre, "arranque", "listo",
		registro.D("direccion", direccion),
		registro.D("bordes", nombresDe(o.cfg.Bordes)),
		registro.D("timeout", o.cfg.TimeoutSegundos),
		registro.D("cifrado", o.cfg.Cifrado))
}

// ---------------------------------------------------------------- reglas

// Responder entrega el archivo actual, confirma la misma versión, o dice
// que no existe.
// Entra: pedido_id (lo copia el borde desde el cliente), el recurso y la
// versión local del borde (nil si pide el archivo entero).
// Sale: Respuesta. Con versión local igual a la actual, Misma=true y sin
// bytes; si no, los bytes. Si falta el archivo, Existe=false.
// Si el otro nodo no contesta: no aplica; solo lee disco local.
func (o *Origen) Responder(pedidoID, recurso string, versionLocal *int) Respuesta {
	ruta, ok := o.rutaSegura(recurso)
	if !ok {
		registro.Registrar(Nombre, pedidoID, "responde", registro.D("recurso", recurso),
			registro.D("resultado", protocolo.FileDoesntExist))
		return Respuesta{}
	}
	contenido, err := os.ReadFile(ruta)
	if err != nil {
		registro.Registrar(Nombre, pedidoID, "responde", registro.D("recurso", recurso),
			registro.D("resultado", protocolo.FileDoesntExist))
		return Respuesta{}
	}
	version := o.versionDe(recurso, contenido)
	if versionLocal != nil && *versionLocal == version {
		registro.Registrar(Nombre, pedidoID, "responde", registro.D("recurso", recurso),
			registro.D("version", version), registro.D("misma", "si"))
		return Respuesta{Existe: true, Misma: true, Version: version}
	}
	datos := []registro.Dato{registro.D("recurso", recurso), registro.D("version", version)}
	if versionLocal != nil {
		datos = append(datos, registro.D("misma", "no"))
	}
	registro.Registrar(Nombre, pedidoID, "responde", datos...)
	return Respuesta{Existe: true, Version: version, Contenido: contenido}
}

// Publicar crea o reemplaza el archivo, sube la versión si los bytes
// cambiaron y avisa a los bordes.
// Entra: pedido_id, recurso y los bytes. Sale: la versión nueva y el aviso.
// Si el otro nodo no contesta: ver Invalidar.
func (o *Origen) Publicar(pedidoID, recurso string, contenido []byte) (int, Aviso, error) {
	ruta, ok := o.rutaSegura(recurso)
	if !ok {
		return 0, Aviso{}, errors.New("nombre de recurso no válido")
	}
	if err := os.WriteFile(ruta, contenido, 0o644); err != nil {
		return 0, Aviso{}, err
	}
	version := o.versionDe(recurso, contenido)
	registro.Registrar(Nombre, pedidoID, "publica", registro.D("recurso", recurso),
		registro.D("version", version), registro.D("bytes", len(contenido)))
	return version, o.Invalidar(pedidoID, recurso), nil
}

// Borrar quita el archivo y avisa a los bordes. La entrada de versión se
// conserva: si el recurso vuelve con otro contenido, la versión sigue subiendo.
// Entra: pedido_id y recurso. Sale: si existía, y el aviso.
func (o *Origen) Borrar(pedidoID, recurso string) (bool, Aviso) {
	ruta, ok := o.rutaSegura(recurso)
	if !ok {
		return false, Aviso{}
	}
	err := os.Remove(ruta)
	existia := err == nil
	registro.Registrar(Nombre, pedidoID, "borra", registro.D("recurso", recurso),
		registro.D("existia", siNo(existia)))
	return existia, o.Invalidar(pedidoID, recurso)
}

// Invalidar avisa a cada borde de la configuración que su copia del
// recurso ya no vale, con el plazo del transporte, y anota la lista de los
// que lo aplicaron.
// Entra: pedido_id y recurso. Sale: Aviso con la versión actual (o
// Existe=false) y los bordes que contestaron 200.
// Si el otro nodo no contesta: deja timeout o nodo_caido con destino=<borde>
// y sigue con el siguiente; ese borde no entra en bordes=.
func (o *Origen) Invalidar(pedidoID, recurso string) Aviso {
	aviso := Aviso{Recurso: recurso}
	if ruta, ok := o.rutaSegura(recurso); ok {
		if contenido, err := os.ReadFile(ruta); err == nil {
			aviso.Existe = true
			aviso.Version = o.versionDe(recurso, contenido)
		}
	}
	cab := map[string]string{protocolo.CabPedidoID: pedidoID, protocolo.CabNodo: Nombre}
	if aviso.Existe {
		cab[protocolo.CabVersion] = strconv.Itoa(aviso.Version)
	} else {
		cab[protocolo.CabResultado] = protocolo.FileDoesntExist
	}
	for _, b := range o.cfg.Bordes {
		resp, fallo, _ := o.transporte.Enviar(b.Direccion, protocolo.MetodoPost,
			protocolo.RutaInvalidar+recurso, cab, nil)
		if fallo != transporte.SinFallo {
			registro.Registrar(Nombre, pedidoID, fallo.String(), registro.D("destino", b.Nombre),
				registro.D("segundos", o.cfg.TimeoutSegundos))
			continue
		}
		if resp.Estado == http.StatusOK {
			quien := strings.TrimSpace(string(resp.Cuerpo))
			if quien == "" {
				quien = b.Nombre
			}
			aviso.Avisados = append(aviso.Avisados, quien)
		}
		// 202 u otro estado: el borde contestó pero no aplicó el aviso.
		// Él anota invalidacion_perdida; aquí no cuenta como avisado.
	}
	datos := []registro.Dato{registro.D("recurso", recurso)}
	if aviso.Existe {
		datos = append(datos, registro.D("version", aviso.Version))
	} else {
		datos = append(datos, registro.D("resultado", protocolo.FileDoesntExist))
	}
	lista := "ninguno"
	if len(aviso.Avisados) > 0 {
		lista = strings.Join(aviso.Avisados, ",")
	}
	datos = append(datos, registro.D("bordes", lista))
	registro.Registrar(Nombre, pedidoID, "invalidar", datos...)
	return aviso
}

// ------------------------------------------------------------------ HTTP

// Manejador devuelve el http.Handler del origen: GET, PUT y DELETE sobre
// /<recurso>. Traduce entre HTTP y las reglas de arriba; no decide nada.
func (o *Origen) Manejador() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		recurso := strings.TrimPrefix(r.URL.Path, "/")
		pedidoID := r.Header.Get(protocolo.CabPedidoID)
		if pedidoID == "" {
			pedidoID = "sin-id"
		}
		w.Header().Set(protocolo.CabPedidoID, pedidoID)
		w.Header().Set(protocolo.CabNodo, Nombre)
		if recurso == "" || strings.Contains(recurso, "/") {
			http.Error(w, "recurso no válido", http.StatusBadRequest)
			return
		}
		switch r.Method {
		case protocolo.MetodoGet:
			var versionLocal *int
			if v := r.Header.Get(protocolo.CabVersionLocal); v != "" {
				if n, err := strconv.Atoi(v); err == nil {
					versionLocal = &n
				}
			}
			resp := o.Responder(pedidoID, recurso, versionLocal)
			if !resp.Existe {
				w.Header().Set(protocolo.CabResultado, protocolo.FileDoesntExist)
				w.WriteHeader(http.StatusNotFound)
				return
			}
			w.Header().Set(protocolo.CabVersion, strconv.Itoa(resp.Version))
			if resp.Misma {
				w.Header().Set(protocolo.CabMisma, "si")
				w.WriteHeader(http.StatusNotModified)
				return
			}
			if versionLocal != nil {
				w.Header().Set(protocolo.CabMisma, "no")
			}
			w.Header().Set("Content-Type", "application/octet-stream")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(resp.Contenido)
		case protocolo.MetodoPut:
			cuerpo, err := io.ReadAll(r.Body)
			if err != nil {
				http.Error(w, "no se pudo leer el cuerpo", http.StatusBadRequest)
				return
			}
			version, aviso, err := o.Publicar(pedidoID, recurso, cuerpo)
			if err != nil {
				http.Error(w, err.Error(), http.StatusBadRequest)
				return
			}
			w.Header().Set(protocolo.CabVersion, strconv.Itoa(version))
			w.Header().Set(protocolo.CabBordes, strings.Join(aviso.Avisados, ","))
			w.WriteHeader(http.StatusOK)
			fmt.Fprintf(w, "%s version=%d bordes=%s\n", recurso, version, strings.Join(aviso.Avisados, ","))
		case protocolo.MetodoDelete:
			existia, aviso := o.Borrar(pedidoID, recurso)
			w.Header().Set(protocolo.CabBordes, strings.Join(aviso.Avisados, ","))
			if !existia {
				w.Header().Set(protocolo.CabResultado, protocolo.FileDoesntExist)
				w.WriteHeader(http.StatusNotFound)
				return
			}
			w.WriteHeader(http.StatusOK)
			fmt.Fprintf(w, "%s borrado bordes=%s\n", recurso, strings.Join(aviso.Avisados, ","))
		default:
			w.Header().Set("Allow", "GET, PUT, DELETE")
			http.Error(w, "método no permitido", http.StatusMethodNotAllowed)
		}
	})
}

// -------------------------------------------------------------- internos

// rutaSegura resuelve el recurso dentro de la carpeta sin salir de ella.
func (o *Origen) rutaSegura(recurso string) (string, bool) {
	if recurso == "" || recurso != filepath.Base(recurso) || strings.HasPrefix(recurso, ".") {
		return "", false
	}
	if strings.ContainsAny(recurso, `/\`) || recurso == "." || recurso == ".." {
		return "", false
	}
	return filepath.Join(o.dir, recurso), true
}

// versionDe devuelve la versión actual del recurso para estos bytes: si el
// hash cambió respecto al último visto, sube en 1 y se persiste; si es la
// primera vez, empieza en 1.
func (o *Origen) versionDe(recurso string, contenido []byte) int {
	suma := sha256.Sum256(contenido)
	huella := hex.EncodeToString(suma[:])
	o.mu.Lock()
	defer o.mu.Unlock()
	e, hay := o.versiones[recurso]
	switch {
	case !hay:
		e = entrada{Version: 1, Hash: huella}
	case e.Hash != huella:
		e = entrada{Version: e.Version + 1, Hash: huella}
	default:
		return e.Version
	}
	o.versiones[recurso] = e
	o.persistir()
	return e.Version
}

// persistir escribe .versiones.json. Se llama con el cerrojo tomado.
func (o *Origen) persistir() {
	datos, err := json.MarshalIndent(o.versiones, "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(filepath.Join(o.dir, archivoVersiones), datos, 0o644)
}

func nombresDe(bordes []config.Borde) string {
	n := make([]string, 0, len(bordes))
	for _, b := range bordes {
		n = append(n, b.Nombre)
	}
	return strings.Join(n, ",")
}

func siNo(b bool) string {
	if b {
		return "si"
	}
	return "no"
}

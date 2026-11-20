// Package transporte es el único sitio de la fase 2 que abre conexiones de
// red hacia otro nodo: envuelve el cliente HTTP de la biblioteca estándar
// con el tiempo de espera de la configuración y clasifica el fallo.
//
// Responsabilidad: Enviar(destino, método, ruta, cabeceras, cuerpo) y
// devolver estado, cabeceras y cuerpo, o decir por qué no hubo respuesta:
// Timeout (venció el plazo) o NodoCaido (la conexión no se pudo abrir o se
// cortó). La lógica de caché, versiones, invalidación y registro no abre
// sockets ni sabe si el canal va en claro o cifrado: con cifrado=false las
// URL son http://; TLS (el plus) solo cambiaría este paquete.
// No reintenta: el reintento es decisión de quien llama.
package transporte

import (
	"bytes"
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"time"
)

// Fallo es la clase de «no responde» que vio quien llamó.
type Fallo int

const (
	// SinFallo: hubo respuesta HTTP, aunque sea un 404 o un 503.
	SinFallo Fallo = iota
	// Timeout: la respuesta no llegó en el plazo.
	Timeout
	// NodoCaido: no se pudo abrir la conexión o se cortó antes de responder.
	NodoCaido
)

// String devuelve el token del historial: timeout o nodo_caido.
func (f Fallo) String() string {
	switch f {
	case Timeout:
		return "timeout"
	case NodoCaido:
		return "nodo_caido"
	}
	return ""
}

// Respuesta es lo que volvió del otro nodo.
type Respuesta struct {
	Estado    int
	Cabeceras http.Header
	Cuerpo    []byte
}

// Transporte es un cliente HTTP con plazo. Entra (al crearlo): el plazo y
// si el canal va cifrado. Sale: Enviar.
type Transporte struct {
	cliente *http.Client
	esquema string
	plazo   time.Duration
}

// Nuevo crea el transporte. cifrado=true no está implementado en esta fase:
// las URL seguirían siendo http y la configuración lo deja en false.
func Nuevo(plazo time.Duration, cifrado bool) *Transporte {
	esquema := "http"
	if cifrado {
		esquema = "https"
	}
	return &Transporte{
		cliente: &http.Client{Timeout: plazo},
		esquema: esquema,
		plazo:   plazo,
	}
}

// Enviar manda un mensaje a destino (host:puerto) y espera la respuesta.
// Entra: destino, método, ruta (empieza por /), cabeceras y cuerpo (puede ser nil).
// Sale: la respuesta, o el Fallo y el error si no la hubo.
// Si el otro nodo no contesta: devuelve Timeout o NodoCaido; no reintenta.
func (t *Transporte) Enviar(destino, metodo, ruta string, cabeceras map[string]string, cuerpo []byte) (*Respuesta, Fallo, error) {
	ctx, cancelar := context.WithTimeout(context.Background(), t.plazo)
	defer cancelar()
	var lector io.Reader
	if cuerpo != nil {
		lector = bytes.NewReader(cuerpo)
	}
	req, err := http.NewRequestWithContext(ctx, metodo, t.esquema+"://"+destino+ruta, lector)
	if err != nil {
		return nil, NodoCaido, err
	}
	for k, v := range cabeceras {
		if v != "" {
			req.Header.Set(k, v)
		}
	}
	resp, err := t.cliente.Do(req)
	if err != nil {
		return nil, clasificar(err), err
	}
	defer resp.Body.Close()
	datos, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, clasificar(err), err
	}
	return &Respuesta{Estado: resp.StatusCode, Cabeceras: resp.Header, Cuerpo: datos}, SinFallo, nil
}

// clasificar separa el plazo vencido de la conexión que no se pudo abrir.
func clasificar(err error) Fallo {
	if errors.Is(err, context.DeadlineExceeded) {
		return Timeout
	}
	var neterr net.Error
	if errors.As(err, &neterr) && neterr.Timeout() {
		return Timeout
	}
	return NodoCaido
}

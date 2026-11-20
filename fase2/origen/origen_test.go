// Pruebas del origen (F2-S09): respuesta y revalidación sin bytes,
// publicación con invalidación, aviso que un borde no aplica, borde que no
// está, y versión que sobrevive al reinicio. Corren solas: go test ./...
package origen

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/protocolo"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
)

// bordeFalso recibe avisos. aplica=false responde 202 (aviso perdido).
type bordeFalso struct {
	nombre   string
	aplica   bool
	mu       sync.Mutex
	recibido []string
	srv      *httptest.Server
}

func nuevoBordeFalso(t *testing.T, nombre string, aplica bool) *bordeFalso {
	b := &bordeFalso{nombre: nombre, aplica: aplica}
	b.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b.mu.Lock()
		b.recibido = append(b.recibido, r.Method+" "+r.URL.Path+" v="+r.Header.Get(protocolo.CabVersion)+
			" res="+r.Header.Get(protocolo.CabResultado))
		b.mu.Unlock()
		if !b.aplica {
			w.WriteHeader(http.StatusAccepted)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, b.nombre)
	}))
	t.Cleanup(b.srv.Close)
	return b
}

func (b *bordeFalso) direccion() string { return strings.TrimPrefix(b.srv.URL, "http://") }

func preparar(t *testing.T, bordes ...config.Borde) (*Origen, string) {
	t.Helper()
	dir := t.TempDir()
	registro.Configurar(filepath.Join(dir, "logs"))
	registro.Consola = nil
	cfg := &config.Config{Origen: "127.0.0.1:0", Bordes: bordes, TimeoutSegundos: 0.5,
		Contenido: filepath.Join(dir, "contenido"), Logs: filepath.Join(dir, "logs")}
	if len(cfg.Bordes) == 0 {
		cfg.Bordes = []config.Borde{{Nombre: "borde-x", Direccion: "127.0.0.1:1"}}
	}
	o, err := Nuevo(cfg)
	if err != nil {
		t.Fatal(err)
	}
	return o, dir
}

func escribir(t *testing.T, dir, nombre, texto string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, "contenido", nombre), []byte(texto), 0o644); err != nil {
		t.Fatal(err)
	}
}

func lineas(t *testing.T, dir, nodo string) string {
	datos, _ := os.ReadFile(filepath.Join(dir, "logs", nodo+".log"))
	return string(datos)
}

func TestResponderYRevalidarSinBytes(t *testing.T) {
	o, dir := preparar(t)
	escribir(t, dir, "apunte.txt", "uno")
	srv := httptest.NewServer(o.Manejador())
	defer srv.Close()

	// Bajada normal: 200, bytes y versión 1.
	resp, _ := http.Get(srv.URL + "/apunte.txt")
	cuerpo, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 || string(cuerpo) != "uno" || resp.Header.Get(protocolo.CabVersion) != "1" {
		t.Fatalf("bajada: estado=%d cuerpo=%q version=%s", resp.StatusCode, cuerpo, resp.Header.Get(protocolo.CabVersion))
	}
	// Revalidación con la misma versión: 304 sin cuerpo.
	req, _ := http.NewRequest("GET", srv.URL+"/apunte.txt", nil)
	req.Header.Set(protocolo.CabVersionLocal, "1")
	req.Header.Set(protocolo.CabPedidoID, "rev-1")
	resp, _ = http.DefaultClient.Do(req)
	cuerpo, _ = io.ReadAll(resp.Body)
	if resp.StatusCode != 304 || len(cuerpo) != 0 || resp.Header.Get(protocolo.CabMisma) != "si" {
		t.Fatalf("misma: estado=%d bytes=%d misma=%s", resp.StatusCode, len(cuerpo), resp.Header.Get(protocolo.CabMisma))
	}
	// El archivo cambia por fuera: la versión sube y viajan bytes.
	escribir(t, dir, "apunte.txt", "dos")
	resp, _ = http.DefaultClient.Do(req)
	cuerpo, _ = io.ReadAll(resp.Body)
	if resp.StatusCode != 200 || string(cuerpo) != "dos" || resp.Header.Get(protocolo.CabVersion) != "2" || resp.Header.Get(protocolo.CabMisma) != "no" {
		t.Fatalf("otra: estado=%d cuerpo=%q version=%s", resp.StatusCode, cuerpo, resp.Header.Get(protocolo.CabVersion))
	}
	// No existe: 404 y file_doesnt_exist.
	resp, _ = http.Get(srv.URL + "/no-existe.txt")
	if resp.StatusCode != 404 || resp.Header.Get(protocolo.CabResultado) != protocolo.FileDoesntExist {
		t.Fatalf("no existe: estado=%d resultado=%s", resp.StatusCode, resp.Header.Get(protocolo.CabResultado))
	}
	hist := lineas(t, dir, "origen")
	for _, esperado := range []string{"responde recurso=apunte.txt version=1", "pedido=rev-1 responde recurso=apunte.txt version=1 misma=si",
		"responde recurso=apunte.txt version=2 misma=no", "responde recurso=no-existe.txt resultado=file_doesnt_exist"} {
		if !strings.Contains(hist, esperado) {
			t.Errorf("falta en el historial: %s\n%s", esperado, hist)
		}
	}
}

func TestPublicarInvalidaALosBordes(t *testing.T) {
	b1 := nuevoBordeFalso(t, "borde-1", true)
	b2 := nuevoBordeFalso(t, "borde-2", true)
	o, dir := preparar(t, config.Borde{Nombre: "borde-1", Direccion: b1.direccion()},
		config.Borde{Nombre: "borde-2", Direccion: b2.direccion()})
	srv := httptest.NewServer(o.Manejador())
	defer srv.Close()

	put := func(texto string) *http.Response {
		req, _ := http.NewRequest("PUT", srv.URL+"/nuevo.txt", strings.NewReader(texto))
		req.Header.Set(protocolo.CabPedidoID, "pub-1")
		resp, _ := http.DefaultClient.Do(req)
		_, _ = io.ReadAll(resp.Body)
		return resp
	}
	if r := put("hola"); r.StatusCode != 200 || r.Header.Get(protocolo.CabVersion) != "1" || r.Header.Get(protocolo.CabBordes) != "borde-1,borde-2" {
		t.Fatalf("put 1: estado=%d version=%s bordes=%s", r.StatusCode, r.Header.Get(protocolo.CabVersion), r.Header.Get(protocolo.CabBordes))
	}
	if r := put("hola"); r.Header.Get(protocolo.CabVersion) != "1" {
		t.Fatalf("mismo contenido no sube la versión: %s", r.Header.Get(protocolo.CabVersion))
	}
	if r := put("adios"); r.Header.Get(protocolo.CabVersion) != "2" {
		t.Fatalf("otro contenido sube a 2: %s", r.Header.Get(protocolo.CabVersion))
	}
	if len(b1.recibido) != 3 || !strings.Contains(b1.recibido[2], "POST /_invalidar/nuevo.txt v=2") {
		t.Fatalf("avisos a borde-1: %v", b1.recibido)
	}
	// DELETE: 200, aviso con file_doesnt_exist, y después GET da 404.
	req, _ := http.NewRequest("DELETE", srv.URL+"/nuevo.txt", nil)
	resp, _ := http.DefaultClient.Do(req)
	_, _ = io.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		t.Fatalf("delete: %d", resp.StatusCode)
	}
	if !strings.Contains(b2.recibido[len(b2.recibido)-1], "res=file_doesnt_exist") {
		t.Fatalf("aviso de borrado: %v", b2.recibido)
	}
	resp, _ = http.Get(srv.URL + "/nuevo.txt")
	if resp.StatusCode != 404 {
		t.Fatalf("tras borrar: %d", resp.StatusCode)
	}
	// Vuelve con otro contenido: la versión sigue subiendo (3), no vuelve a 1.
	if r := put("otra vez"); r.Header.Get(protocolo.CabVersion) != "3" {
		t.Fatalf("tras borrar y volver: %s", r.Header.Get(protocolo.CabVersion))
	}
	hist := lineas(t, dir, "origen")
	if !strings.Contains(hist, "invalidar recurso=nuevo.txt version=2 bordes=borde-1,borde-2") ||
		!strings.Contains(hist, "invalidar recurso=nuevo.txt resultado=file_doesnt_exist bordes=borde-1,borde-2") {
		t.Errorf("historial de invalidar:\n%s", hist)
	}
}

func TestAvisoPerdidoYBordeQueNoEsta(t *testing.T) {
	aplica := nuevoBordeFalso(t, "borde-1", true)
	pierde := nuevoBordeFalso(t, "borde-2", false) // contesta 202: recibido, no aplicado
	o, dir := preparar(t,
		config.Borde{Nombre: "borde-1", Direccion: aplica.direccion()},
		config.Borde{Nombre: "borde-2", Direccion: pierde.direccion()},
		config.Borde{Nombre: "borde-3", Direccion: "127.0.0.1:1"}) // nadie escucha
	escribir(t, dir, "a.txt", "x")
	inicio := time.Now()
	aviso := o.Invalidar("inv-1", "a.txt")
	if strings.Join(aviso.Avisados, ",") != "borde-1" {
		t.Fatalf("avisados: %v", aviso.Avisados)
	}
	if time.Since(inicio) > 3*time.Second {
		t.Fatalf("el borde que no está no puede bloquear: %v", time.Since(inicio))
	}
	hist := lineas(t, dir, "origen")
	if !strings.Contains(hist, "nodo_caido destino=borde-3") || !strings.Contains(hist, "invalidar recurso=a.txt version=1 bordes=borde-1") {
		t.Errorf("historial:\n%s", hist)
	}
}

func TestVersionSobreviveAlReinicio(t *testing.T) {
	o, dir := preparar(t)
	escribir(t, dir, "p.txt", "v1")
	o.Responder("a", "p.txt", nil)
	escribir(t, dir, "p.txt", "v2")
	if r := o.Responder("b", "p.txt", nil); r.Version != 2 {
		t.Fatalf("esperaba 2, hay %d", r.Version)
	}
	// «Reinicio»: otro Origen sobre la misma carpeta.
	o2, err := Nuevo(o.cfg)
	if err != nil {
		t.Fatal(err)
	}
	if r := o2.Responder("c", "p.txt", nil); r.Version != 2 {
		t.Fatalf("tras reiniciar esperaba 2, hay %d", r.Version)
	}
	dos := 2
	if r := o2.Responder("d", "p.txt", &dos); !r.Misma {
		t.Fatalf("tras reiniciar la versión 2 tiene que seguir siendo la misma")
	}
}

func TestNombresPeligrosos(t *testing.T) {
	o, _ := preparar(t)
	srv := httptest.NewServer(o.Manejador())
	defer srv.Close()
	for _, ruta := range []string{"/.versiones.json", "/..%2Fgo.mod", "/a/b"} {
		resp, _ := http.Get(srv.URL + ruta)
		if resp.StatusCode == 200 {
			t.Errorf("%s no debería servirse", ruta)
		}
	}
	if _, _, err := o.Publicar("p", "../fuera.txt", []byte("x")); err == nil {
		t.Errorf("publicar fuera de la carpeta tiene que fallar")
	}
}

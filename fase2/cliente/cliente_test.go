// Pruebas del cliente y del selector (F2-S08): borde que rechaza, borde
// que no está, borde que entrega, y el orden del selector.
package cliente

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/protocolo"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
)

func bordeQue(t *testing.T, estado int, resultado, version, cuerpo string) string {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set(protocolo.CabResultado, resultado)
		if version != "" {
			w.Header().Set(protocolo.CabVersion, version)
		}
		w.Header().Set(protocolo.CabPedidoID, r.Header.Get(protocolo.CabPedidoID))
		w.WriteHeader(estado)
		_, _ = w.Write([]byte(cuerpo))
	}))
	t.Cleanup(srv.Close)
	return strings.TrimPrefix(srv.URL, "http://")
}

func clienteCon(t *testing.T, bordes ...config.Borde) (*Cliente, string) {
	dir := t.TempDir()
	registro.Configurar(filepath.Join(dir, "logs"))
	registro.Consola = nil
	cfg := &config.Config{Origen: "x", Bordes: bordes, TimeoutSegundos: 0.5, EvitarBordeSegundos: 10}
	return Nuevo("cliente", cfg), dir
}

func historial(dir string) string {
	d, _ := os.ReadFile(filepath.Join(dir, "logs", "cliente.log"))
	return string(d)
}

func TestBordeCaidoYElOtroEntrega(t *testing.T) {
	c, dir := clienteCon(t,
		config.Borde{Nombre: "borde-1", Direccion: "127.0.0.1:1"},
		config.Borde{Nombre: "borde-2", Direccion: bordeQue(t, 200, protocolo.Miss, "1", "hola")})
	r := c.Pedir("apunte.txt", "p1")
	if r.Resultado != protocolo.Miss || r.Fuente != "borde-2" || string(r.Contenido) != "hola" || r.Version != 1 {
		t.Fatalf("respuesta: %+v", r)
	}
	h := historial(dir)
	for _, e := range []string{"pedido=p1 solicitud recurso=apunte.txt fuente=borde-1", "pedido=p1 nodo_caido destino=borde-1",
		"pedido=p1 solicitud recurso=apunte.txt fuente=borde-2", "pedido=p1 respuesta version=1 resultado=miss fuente=borde-2"} {
		if !strings.Contains(h, e) {
			t.Errorf("falta: %s\n%s", e, h)
		}
	}
	// El segundo pedido va directo a borde-2: borde-1 queda evitado.
	c.Pedir("apunte.txt", "p2")
	if strings.Contains(historial(dir), "pedido=p2 solicitud recurso=apunte.txt fuente=borde-1") {
		t.Errorf("borde-1 debería estar al final de la lista")
	}
}

func TestRechazaDeUnBordeNoEsFinal(t *testing.T) {
	c, dir := clienteCon(t,
		config.Borde{Nombre: "borde-1", Direccion: bordeQue(t, 503, protocolo.Rechaza, "", "")},
		config.Borde{Nombre: "borde-2", Direccion: bordeQue(t, 200, protocolo.SirveObsoleta, "3", "viejo")})
	r := c.Pedir("a.txt", "p3")
	if r.Resultado != protocolo.SirveObsoleta || r.Fuente != "borde-2" || r.Version != 3 {
		t.Fatalf("respuesta: %+v", r)
	}
	if !strings.Contains(historial(dir), "respuesta version=3 resultado=sirve_obsoleta fuente=borde-2") {
		t.Errorf("historial:\n%s", historial(dir))
	}
}

func TestTodosRechazanOCaen(t *testing.T) {
	c, dir := clienteCon(t,
		config.Borde{Nombre: "borde-1", Direccion: bordeQue(t, 503, protocolo.Rechaza, "", "")},
		config.Borde{Nombre: "borde-2", Direccion: "127.0.0.1:1"})
	r := c.Pedir("a.txt", "p4")
	if r.Resultado != protocolo.Rechaza || r.Fuente != "" {
		t.Fatalf("respuesta: %+v", r)
	}
	if !strings.Contains(historial(dir), "pedido=p4 respuesta resultado=rechaza fuente=ninguna") {
		t.Errorf("historial:\n%s", historial(dir))
	}
}

func TestFileDoesntExistSinCuerpo(t *testing.T) {
	c, _ := clienteCon(t, config.Borde{Nombre: "borde-1", Direccion: bordeQue(t, 404, protocolo.FileDoesntExist, "", "no")})
	r := c.Pedir("x.txt", "p5")
	if r.Resultado != protocolo.FileDoesntExist || r.Contenido != nil {
		t.Fatalf("respuesta: %+v", r)
	}
}

func TestSelectorOrden(t *testing.T) {
	s := NuevoSelector([]config.Borde{{Nombre: "a"}, {Nombre: "b"}}, 10*time.Second)
	t0 := time.Now()
	s.ahora = func() time.Time { return t0 }
	s.NoRespondio("a")
	if o := s.Orden(); o[0].Nombre != "b" || o[1].Nombre != "a" {
		t.Fatalf("orden con a evitado: %v", o)
	}
	s.ahora = func() time.Time { return t0.Add(11 * time.Second) }
	if o := s.Orden(); o[0].Nombre != "a" {
		t.Fatalf("a recupera su lugar al pasar el plazo: %v", o)
	}
	s.NoRespondio("a")
	s.Respondio("a")
	if o := s.Orden(); o[0].Nombre != "a" {
		t.Fatalf("a recupera su lugar al contestar: %v", o)
	}
}

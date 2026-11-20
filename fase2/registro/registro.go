// Package registro es el historial compartido de la fase 2: la única función
// que escribe líneas de operación, con el mismo formato del README y de
// fase1/registro.py.
//
// Responsabilidad: armar la línea «hora nodo pedido=… operacion clave=valor…»,
// mostrarla en consola y agregarla a <logs>/<nodo>.log.
// No decide hit, miss, invalidación ni STALE_LIMIT. No abre sockets.
// No guarda el contenido de los archivos repartidos.
package registro

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// Dato es un par clave=valor de la línea. Se pasan en orden, como en Python.
type Dato struct {
	Clave string
	Valor interface{}
}

// D construye un Dato en una llamada corta: registro.D("recurso", nombre).
func D(clave string, valor interface{}) Dato { return Dato{clave, valor} }

var (
	mu  sync.Mutex
	dir = "logs"
	// Salida de consola; las pruebas pueden silenciarla.
	Consola = os.Stdout
)

// Configurar fija la carpeta del historial. Entra: la ruta. Sale: nada.
func Configurar(carpeta string) {
	mu.Lock()
	defer mu.Unlock()
	if carpeta != "" {
		dir = carpeta
	}
}

// Registrar escribe una línea de historial y la muestra.
// Entra: nombre del nodo, pedido_id, operación y los pares clave=valor.
// Sale: la línea escrita, sin salto final.
// Si el otro nodo no contesta: no aplica; esta función no habla con nadie.
func Registrar(nodo, pedidoID, operacion string, datos ...Dato) string {
	hora := time.Now().Format("15:04:05.000")
	partes := []string{hora, nodo, "pedido=" + pedidoID, operacion}
	for _, d := range datos {
		partes = append(partes, fmt.Sprintf("%s=%v", d.Clave, d.Valor))
	}
	linea := strings.Join(partes, " ")

	mu.Lock()
	defer mu.Unlock()
	_ = os.MkdirAll(dir, 0o755)
	ruta := filepath.Join(dir, nodo+".log")
	if f, err := os.OpenFile(ruta, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644); err == nil {
		_, _ = f.WriteString(linea + "\n")
		_ = f.Close()
	}
	if Consola != nil {
		_, _ = fmt.Fprintln(Consola, linea)
	}
	return linea
}

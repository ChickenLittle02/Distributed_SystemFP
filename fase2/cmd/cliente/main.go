// Programa cliente (fase 2): pide un recurso a los bordes de la
// configuración, en el orden del selector, y muestra el resultado.
//
// Responsabilidad: leer la configuración, crear el cliente, hacer uno o
// varios pedidos y dejar solicitud y respuesta en logs/cliente.log. Es el
// «cliente automático» de F2-S05; el navegador hace el mismo GET.
//
//	go run ./fase2/cmd/cliente -config fase2/config.json -recurso apunte.txt [-n 2] [-pedido id] [-guardar salida]
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/cliente"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
)

func main() {
	ruta := flag.String("config", "fase2/config.json", "archivo de configuración")
	recurso := flag.String("recurso", "apunte.txt", "nombre del archivo")
	n := flag.Int("n", 1, "cuántas veces pedirlo")
	pedido := flag.String("pedido", "", "pedido_id fijo (para repetir un pedido); vacío lo crea el cliente")
	nombre := flag.String("nombre", "cliente", "nombre del nodo en el historial")
	guardar := flag.String("guardar", "", "ruta donde escribir los bytes recibidos")
	flag.Parse()

	cfg, err := config.Cargar(*ruta)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	registro.Configurar(cfg.Logs)
	c := cliente.Nuevo(*nombre, cfg)
	c.Listo()
	salida := 0
	for i := 0; i < *n; i++ {
		r := c.Pedir(*recurso, *pedido)
		fmt.Printf("pedido=%s resultado=%s version=%d fuente=%s bytes=%d\n",
			r.PedidoID, r.Resultado, r.Version, r.Fuente, len(r.Contenido))
		if r.Resultado == "rechaza" || r.Resultado == "file_doesnt_exist" {
			salida = 1
		}
		if *guardar != "" && r.Contenido != nil {
			_ = os.WriteFile(*guardar, r.Contenido, 0o644)
		}
	}
	os.Exit(salida)
}

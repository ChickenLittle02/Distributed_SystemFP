// Programa del origen (fase 2): un proceso que escucha HTTP en la dirección
// de la configuración y atiende GET, PUT y DELETE de /<recurso>.
//
// Responsabilidad: leer la configuración, crear el origen, anotar listo y
// servir hasta que lo maten. Es el único sitio que abre el puerto del
// origen. No es el borde ni el cliente.
//
//	go run ./fase2/cmd/origen -config fase2/config.json
package main

import (
	"flag"
	"fmt"
	"net/http"
	"os"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/origen"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
)

func main() {
	ruta := flag.String("config", "fase2/config.json", "archivo de configuración")
	escucha := flag.String("escucha", "", "host:puerto donde escuchar (por defecto, el de la configuración)")
	flag.Parse()

	cfg, err := config.Cargar(*ruta)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	registro.Configurar(cfg.Logs)
	o, err := origen.Nuevo(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	direccion := cfg.Origen
	if *escucha != "" {
		direccion = *escucha
	}
	o.Listo(direccion)
	if err := http.ListenAndServe(direccion, o.Manejador()); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

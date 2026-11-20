// Programa de publicación (fase 2): quien publica habla solo con el
// origen. PUT crea o reemplaza un recurso con el contenido de un archivo
// local; DELETE lo borra. Nunca pasa por un borde.
//
// Responsabilidad: leer la configuración, mandar el PUT o el DELETE por el
// transporte con el plazo configurado, anotar publica/borra en
// logs/publicador.log y mostrar la versión y los bordes avisados que
// devuelve el origen.
//
//	go run ./fase2/cmd/publicar -config fase2/config.json put apunte.txt ./archivo-local
//	go run ./fase2/cmd/publicar -config fase2/config.json delete apunte.txt
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/cliente"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/protocolo"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/transporte"
)

const nombre = "publicador"

func main() {
	ruta := flag.String("config", "fase2/config.json", "archivo de configuración")
	flag.Parse()
	args := flag.Args()
	if len(args) < 2 {
		fmt.Fprintln(os.Stderr, "uso: publicar [-config f] put <recurso> <archivo-local> | delete <recurso>")
		os.Exit(2)
	}
	cfg, err := config.Cargar(*ruta)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	registro.Configurar(cfg.Logs)
	t := transporte.Nuevo(cfg.Timeout(), cfg.Cifrado)
	pedidoID := cliente.NuevoPedidoID()
	recurso := args[1]
	cab := map[string]string{protocolo.CabPedidoID: pedidoID, protocolo.CabNodo: nombre}

	var metodo string
	var cuerpo []byte
	switch args[0] {
	case "put":
		if len(args) < 3 {
			fmt.Fprintln(os.Stderr, "put necesita el archivo local")
			os.Exit(2)
		}
		cuerpo, err = os.ReadFile(args[2])
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		metodo = protocolo.MetodoPut
		registro.Registrar(nombre, pedidoID, "publica", registro.D("recurso", recurso),
			registro.D("bytes", len(cuerpo)), registro.D("destino", "origen"))
	case "delete":
		metodo = protocolo.MetodoDelete
		registro.Registrar(nombre, pedidoID, "borra", registro.D("recurso", recurso),
			registro.D("destino", "origen"))
	default:
		fmt.Fprintln(os.Stderr, "orden desconocida:", args[0])
		os.Exit(2)
	}
	resp, fallo, err := t.Enviar(cfg.Origen, metodo, "/"+recurso, cab, cuerpo)
	if fallo != transporte.SinFallo {
		registro.Registrar(nombre, pedidoID, fallo.String(), registro.D("destino", "origen"),
			registro.D("segundos", cfg.TimeoutSegundos))
		fmt.Fprintln(os.Stderr, "el origen no responde:", err)
		os.Exit(1)
	}
	registro.Registrar(nombre, pedidoID, "respuesta", registro.D("estado", resp.Estado),
		registro.D("version", resp.Cabeceras.Get(protocolo.CabVersion)),
		registro.D("bordes", resp.Cabeceras.Get(protocolo.CabBordes)))
	fmt.Printf("estado=%d version=%s bordes_avisados=%s\n", resp.Estado,
		resp.Cabeceras.Get(protocolo.CabVersion), resp.Cabeceras.Get(protocolo.CabBordes))
	if resp.Estado >= 400 {
		os.Exit(1)
	}
}

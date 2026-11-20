// Package cliente es quien quiere el archivo en la fase 2: un programa que
// pide GET /<recurso> al borde que diga el selector, pasa al siguiente si
// ese no responde (timeout, nodo_caido) o rechaza, y anota solicitud y
// respuesta con el pedido_id que él mismo crea.
//
// Responsabilidad: crear el pedido_id, recorrer el orden del selector,
// mandar el GET por el transporte y traducir la respuesta HTTP al contrato
// (resultado, versión, bytes). El navegador del lector hace lo mismo sin
// este programa: el borde le crea el pedido_id si no manda X-Pedido-Id.
// No guarda caché, no numera versiones, no aplica STALE_LIMIT y no habla
// con el origen: el origen no es una fuente del selector.
package cliente

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strconv"
	"time"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/protocolo"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/registro"
	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/transporte"
)

// Respuesta es lo que ve quien pidió: el contrato de docs/contrato.md.
type Respuesta struct {
	PedidoID  string
	Resultado string
	Version   int
	Contenido []byte
	Fuente    string // borde que entregó; "" si rechaza
}

// Cliente es el programa cliente. Entra (al crearlo): nombre del nodo y la
// configuración. Sale: Pedir. Si el otro nodo no contesta: pasa al
// siguiente borde del selector; si ninguno entrega, rechaza.
type Cliente struct {
	Nombre     string
	cfg        *config.Config
	selector   *Selector
	transporte *transporte.Transporte
}

// Nuevo crea el cliente con el selector y el transporte de la configuración.
func Nuevo(nombre string, cfg *config.Config) *Cliente {
	return &Cliente{
		Nombre:     nombre,
		cfg:        cfg,
		selector:   NuevoSelector(cfg.Bordes, duracion(cfg.EvitarBordeSegundos)),
		transporte: transporte.Nuevo(cfg.Timeout(), cfg.Cifrado),
	}
}

// Listo deja la línea de arranque.
func (c *Cliente) Listo() {
	nombres := ""
	for i, b := range c.cfg.Bordes {
		if i > 0 {
			nombres += ","
		}
		nombres += b.Nombre
	}
	registro.Registrar(c.Nombre, "arranque", "listo", registro.D("bordes", nombres),
		registro.D("timeout", c.cfg.TimeoutSegundos))
}

// Pedir pide un recurso y devuelve la respuesta final.
// Entra: el recurso y un pedido_id opcional ("" para que el cliente lo cree;
// darlo sirve para repetir un pedido en las pruebas).
// Sale: Respuesta con resultado, versión, bytes y fuente.
// Si el otro nodo no contesta: anota timeout o nodo_caido con destino=<borde>
// y sigue con el siguiente; si ningún borde entrega, respuesta resultado=rechaza.
func (c *Cliente) Pedir(recurso, pedidoID string) Respuesta {
	if pedidoID == "" {
		pedidoID = NuevoPedidoID()
	}
	for _, b := range c.selector.Orden() {
		registro.Registrar(c.Nombre, pedidoID, "solicitud", registro.D("recurso", recurso),
			registro.D("fuente", b.Nombre))
		resp, fallo, _ := c.transporte.Enviar(b.Direccion, protocolo.MetodoGet, "/"+recurso,
			map[string]string{protocolo.CabPedidoID: pedidoID, protocolo.CabNodo: c.Nombre}, nil)
		if fallo != transporte.SinFallo {
			registro.Registrar(c.Nombre, pedidoID, fallo.String(), registro.D("destino", b.Nombre),
				registro.D("segundos", c.cfg.TimeoutSegundos))
			c.selector.NoRespondio(b.Nombre)
			continue
		}
		c.selector.Respondio(b.Nombre)
		resultado := resp.Cabeceras.Get(protocolo.CabResultado)
		if resultado == "" {
			resultado = resultadoPorEstado(resp.Estado)
		}
		if resultado == protocolo.Rechaza {
			// El rechaza de un borde no es final: el contrato dice probar el otro.
			continue
		}
		version, _ := strconv.Atoi(resp.Cabeceras.Get(protocolo.CabVersion))
		datos := []registro.Dato{}
		if version > 0 {
			datos = append(datos, registro.D("version", version))
		}
		datos = append(datos, registro.D("resultado", resultado), registro.D("fuente", b.Nombre))
		registro.Registrar(c.Nombre, pedidoID, "respuesta", datos...)
		r := Respuesta{PedidoID: pedidoID, Resultado: resultado, Version: version, Fuente: b.Nombre}
		if resultado != protocolo.FileDoesntExist {
			r.Contenido = resp.Cuerpo
		}
		return r
	}
	registro.Registrar(c.Nombre, pedidoID, "respuesta", registro.D("resultado", protocolo.Rechaza),
		registro.D("fuente", "ninguna"))
	return Respuesta{PedidoID: pedidoID, Resultado: protocolo.Rechaza}
}

// resultadoPorEstado cubre un borde que no puso X-Resultado.
func resultadoPorEstado(estado int) string {
	switch {
	case estado == http.StatusNotFound:
		return protocolo.FileDoesntExist
	case estado >= 500:
		return protocolo.Rechaza
	default:
		return protocolo.Hit
	}
}

// NuevoPedidoID crea un identificador corto (6 hex), como en la fase 1.
func NuevoPedidoID() string {
	b := make([]byte, 3)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func duracion(segundos float64) time.Duration { return durSeg(segundos) }

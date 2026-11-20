// Package protocolo fija los nombres que viajan por HTTP entre los nodos de
// la fase 2: cabeceras, resultados y rutas. Es el «formato de mensaje como
// texto» de F2-S02: recurso en la ruta, versión y pedido_id en cabeceras,
// el archivo en el cuerpo.
//
// Responsabilidad: que origen, borde, cliente y pruebas usen las mismas
// cadenas. No abre sockets ni decide nada.
//
// Los dos canales (docs/diseno-nativo.md, «Protocolo»):
//
//	lector  → borde   GET /<recurso>            cabecera opcional X-Pedido-Id
//	borde   → origen  GET /<recurso>            X-Pedido-Id, opcional X-Version-Local
//	publica → origen  PUT /<recurso> (cuerpo)   DELETE /<recurso>
//	origen  → borde   POST /_invalidar/<recurso>  X-Pedido-Id, X-Version o X-Resultado=file_doesnt_exist
//
// Respuestas del origen a un GET: 200 con el archivo y X-Version; 304 sin
// cuerpo con X-Version y X-Misma=si cuando la versión local coincide; 404
// con X-Resultado=file_doesnt_exist. Respuestas del borde a un GET: 200 con
// X-Resultado hit|miss|sirve_obsoleta; 404 file_doesnt_exist; 503 rechaza.
// Respuesta del borde a un aviso: 200 y su nombre en el cuerpo si lo aplicó;
// 202 si lo recibió y no lo aplicó (aviso perdido simulado); cualquier otra
// cosa, o ninguna, cuenta como «no contestó».
package protocolo

// Cabeceras HTTP del proyecto.
const (
	CabPedidoID     = "X-Pedido-Id"
	CabVersion      = "X-Version"
	CabVersionLocal = "X-Version-Local"
	CabMisma        = "X-Misma"
	CabResultado    = "X-Resultado"
	CabFuente       = "X-Fuente"
	CabBordes       = "X-Bordes-Avisados"
	CabNodo         = "X-Nodo"
)

// Resultados que ve el cliente (docs/contrato.md) y tokens del historial.
const (
	Hit             = "hit"
	Miss            = "miss"
	SirveObsoleta   = "sirve_obsoleta"
	Rechaza         = "rechaza"
	FileDoesntExist = "file_doesnt_exist"
)

// Prefijo de la ruta del aviso de invalidación en el borde.
const RutaInvalidar = "/_invalidar/"

// Métodos.
const (
	MetodoGet    = "GET"
	MetodoPut    = "PUT"
	MetodoDelete = "DELETE"
	MetodoPost   = "POST"
)

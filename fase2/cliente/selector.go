// Selector de fuente de la fase 2: en qué orden el cliente prueba los
// bordes. Misma política que fase1/selector.py (docs/decisiones.md, 19 nov):
// orden fijo de la configuración; el que no respondió va al final durante
// evitar_borde_segundos; nunca se descarta. Vive en el proceso del cliente;
// no es un nodo, no llama a nadie y no decide hit, miss ni obsoleto.
package cliente

import (
	"time"

	"github.com/ChickenLittle02/Distributed_SystemFP/fase2/config"
)

// Selector ordena bordes. Entra (al crearlo): los bordes en orden de
// preferencia y cuánto se evita al que no respondió. Sale: Orden,
// NoRespondio, Respondio. Si el otro nodo no contesta: no aplica.
type Selector struct {
	bordes   []config.Borde
	evitar   time.Duration
	evitados map[string]time.Time
	ahora    func() time.Time
}

// NuevoSelector crea el selector con la lista de la configuración.
func NuevoSelector(bordes []config.Borde, evitar time.Duration) *Selector {
	return &Selector{bordes: bordes, evitar: evitar, evitados: map[string]time.Time{}, ahora: time.Now}
}

// Orden devuelve los bordes para este pedido: la preferencia fija, con los
// que no respondieron hace poco movidos al final.
func (s *Selector) Orden() []config.Borde {
	ahora := s.ahora()
	buenos := make([]config.Borde, 0, len(s.bordes))
	malos := make([]config.Borde, 0)
	for _, b := range s.bordes {
		if hasta, ok := s.evitados[b.Nombre]; ok && hasta.After(ahora) {
			malos = append(malos, b)
		} else {
			buenos = append(buenos, b)
		}
	}
	return append(buenos, malos...)
}

// NoRespondio anota que el borde no contestó: va al final durante evitar.
func (s *Selector) NoRespondio(nombre string) { s.evitados[nombre] = s.ahora().Add(s.evitar) }

// Respondio devuelve su lugar a un borde que contestó (aunque fuera rechaza).
func (s *Selector) Respondio(nombre string) { delete(s.evitados, nombre) }

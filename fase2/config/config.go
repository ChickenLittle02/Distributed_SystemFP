// Package config reúne en un solo sitio los números y las direcciones de la
// corrida nativa: TTL, STALE_LIMIT, capacidad, política de expulsión, tiempo
// de espera, cifrado, la dirección del origen y la lista estática de bordes.
//
// Responsabilidad: leer fase2/config.json (o el archivo que se indique) y
// dejar que las variables de entorno P20_* acorten una corrida de prueba.
// No decide nada: origen, borde, cliente y DNS leen de aquí. La lista de
// bordes es el arranque estático que docs/decisiones.md justifica: nadie
// descubre a nadie; cada nodo sabe la dirección de los demás por este archivo.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"time"
)

// Borde es un nodo de borde conocido de antemano: su nombre en el historial
// y la dirección host:puerto en la que escucha HTTP.
type Borde struct {
	Nombre    string `json:"nombre"`
	Direccion string `json:"direccion"`
}

// Config son los valores de la corrida. Entra: el archivo JSON y el entorno.
// Sale: los campos. Si el otro nodo no contesta: no aplica; no habla con nadie.
type Config struct {
	// Dirección host:puerto del origen.
	Origen string `json:"origen"`
	// Bordes en orden de preferencia: el primero es el «más cercano».
	Bordes []Borde `json:"bordes"`
	// Una copia recién guardada está fresca este tiempo.
	TTLSegundos float64 `json:"ttl_segundos"`
	// Cuánto puede llevar obsoleta una copia para servirla si el origen calla.
	// Cuenta desde que expiró, no desde que se guardó.
	StaleLimitSegundos float64 `json:"stale_limit_segundos"`
	// Copias que caben en un borde.
	Capacidad int `json:"capacidad"`
	// Política de expulsión cuando el borde está lleno.
	Expulsion string `json:"expulsion"`
	// Cuánto espera un nodo la respuesta de otro antes de darlo por «no responde».
	TimeoutSegundos float64 `json:"timeout_segundos"`
	// Cuánto deja el selector al final a un borde que no respondió.
	EvitarBordeSegundos float64 `json:"evitar_borde_segundos"`
	// El canal va en claro. TLS es el plus del README y no entra en esta fase.
	Cifrado bool `json:"cifrado"`
	// Carpeta de la que el origen reparte archivos.
	Contenido string `json:"contenido"`
	// Carpeta del historial, un archivo por nodo.
	Logs string `json:"logs"`
}

// Cargar lee el archivo JSON y aplica las variables P20_TTL, P20_STALE_LIMIT,
// P20_CAPACIDAD, P20_TIMEOUT y P20_EVITAR_BORDE si están puestas.
// Entra: la ruta del archivo. Sale: la configuración o el error de lectura.
func Cargar(ruta string) (*Config, error) {
	datos, err := os.ReadFile(ruta)
	if err != nil {
		return nil, fmt.Errorf("config: no se pudo leer %s: %w", ruta, err)
	}
	c := &Config{}
	if err := json.Unmarshal(datos, c); err != nil {
		return nil, fmt.Errorf("config: %s no es JSON válido: %w", ruta, err)
	}
	c.desdeEntorno()
	if err := c.validar(); err != nil {
		return nil, err
	}
	return c, nil
}

// desdeEntorno sobreescribe los números con P20_* para una corrida corta.
func (c *Config) desdeEntorno() {
	flotante := func(clave string, destino *float64) {
		if v, ok := os.LookupEnv(clave); ok {
			if f, err := strconv.ParseFloat(v, 64); err == nil {
				*destino = f
			}
		}
	}
	flotante("P20_TTL", &c.TTLSegundos)
	flotante("P20_STALE_LIMIT", &c.StaleLimitSegundos)
	flotante("P20_TIMEOUT", &c.TimeoutSegundos)
	flotante("P20_EVITAR_BORDE", &c.EvitarBordeSegundos)
	if v, ok := os.LookupEnv("P20_CAPACIDAD"); ok {
		if n, err := strconv.Atoi(v); err == nil {
			c.Capacidad = n
		}
	}
}

func (c *Config) validar() error {
	if c.Origen == "" {
		return fmt.Errorf("config: falta la dirección del origen")
	}
	if len(c.Bordes) == 0 {
		return fmt.Errorf("config: la lista de bordes está vacía")
	}
	if c.TimeoutSegundos <= 0 {
		return fmt.Errorf("config: timeout_segundos tiene que ser mayor que 0")
	}
	if c.Contenido == "" {
		c.Contenido = "contenido"
	}
	if c.Logs == "" {
		c.Logs = "logs"
	}
	if c.Expulsion == "" {
		c.Expulsion = "LRU"
	}
	return nil
}

// Timeout es TimeoutSegundos como duración.
func (c *Config) Timeout() time.Duration {
	return time.Duration(c.TimeoutSegundos * float64(time.Second))
}

// Esquema es el prefijo de las URL: http en claro; https el día que
// cifrado sea true (TLS, fuera de esta fase).
func (c *Config) Esquema() string {
	if c.Cifrado {
		return "https"
	}
	return "http"
}

// DireccionDe devuelve la dirección de un borde por su nombre, o "" si no está.
func (c *Config) DireccionDe(nombre string) string {
	for _, b := range c.Bordes {
		if b.Nombre == nombre {
			return b.Direccion
		}
	}
	return ""
}

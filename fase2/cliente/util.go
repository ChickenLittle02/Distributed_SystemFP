package cliente

import "time"

// durSeg convierte segundos (float) en time.Duration.
func durSeg(s float64) time.Duration { return time.Duration(s * float64(time.Second)) }

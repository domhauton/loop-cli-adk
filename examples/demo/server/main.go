// Command server serves a local API fixture for the demo CLI.
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /users", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Header.Get("Authorization") != "Bearer demo-local" {
			w.WriteHeader(http.StatusUnauthorized)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "unauthorised"})
			return
		}
		name := r.URL.Query().Get("name")
		if name == "" {
			name = "Ada"
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"users": []map[string]string{{"id": "user-1", "name": name}}})
	})
	server := http.Server{Addr: "127.0.0.1:8080", Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Print("Demo API listening at http://127.0.0.1:8080 (local fixture credential: demo-local)")
	log.Fatal(server.ListenAndServe())
}

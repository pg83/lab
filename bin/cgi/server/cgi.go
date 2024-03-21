package main

import (
	"os"
	"fmt"
	"net/http"
	"net/http/cgi"
)

func cgiHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Println(r)

	handler := cgi.Handler{
		Path: os.Args[2] + r.URL.Path,
	}

	handler.ServeHTTP(w, r)
}

func main() {
	http.HandleFunc("/", cgiHandler)
	http.ListenAndServe(os.Args[1], nil)
}

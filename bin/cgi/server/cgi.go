package main

import (
	"os"
	"fmt"
	"strings"
	"net/http"
	"net/http/cgi"
)

var (
    BAD = []string{"..", "\\"}
)

func sanitize(s string) string {
	for _, b := range BAD {
		if strings.Contains(s, b) {
			panic("we are under attack!")
		}
	}
	return s;
}

func cgiHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Println(r)

	handler := cgi.Handler{
		Path: os.Args[2] + sanitize(r.URL.Path),
		Env: os.Environ(),
	}

	handler.ServeHTTP(w, r)
}

func main() {
	http.HandleFunc("/", cgiHandler)
	http.ListenAndServe(os.Args[1], nil)
}

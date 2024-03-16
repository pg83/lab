package main

import (
	"os"
	"net/http"
)

func main() {
	port := ":" + os.Args[1]
	handler := http.FileServer(http.Dir(os.Args[2]))
	http.ListenAndServe(port, handler)
}

// Independent Go crypto/rsa verification of the Python bridge's PSS encoding.
package main

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	_ "crypto/sha256"
	_ "crypto/sha512"
	"encoding/json"
	"fmt"
	"io"
	"math/big"
	"os"
)

func main() {
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		panic(err)
	}
	dec := json.NewDecoder(os.Stdin)
	n := 0
	for {
		var v struct {
			Encoded, Digest []byte
			Hash            string
			Salt            int
		}
		if err := dec.Decode(&v); err == io.EOF {
			break
		} else if err != nil {
			panic(err)
		}
		hash := map[string]crypto.Hash{"SHA256": crypto.SHA256, "SHA384": crypto.SHA384, "SHA512": crypto.SHA512}[v.Hash]
		if len(v.Encoded) != 256 {
			panic("wrong encoded length")
		}
		// Raw RSA, equivalent to the operation performed by Keychain.
		em := new(big.Int).SetBytes(v.Encoded)
		signature := new(big.Int).Exp(em, key.D, key.N).FillBytes(make([]byte, 256))
		opts := &rsa.PSSOptions{SaltLength: v.Salt, Hash: hash}
		if err := rsa.VerifyPSS(&key.PublicKey, hash, v.Digest, signature, opts); err != nil {
			panic(err)
		}
		v.Digest[0] ^= 1
		if rsa.VerifyPSS(&key.PublicKey, hash, v.Digest, signature, opts) == nil {
			panic("accepted wrong digest")
		}
		n++
	}
	if n != 6 {
		panic("expected six cases")
	}
	fmt.Println("PASS: six PSS combinations independently verified; wrong digests rejected")
}

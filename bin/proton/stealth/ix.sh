{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/26
{% endblock %}

{% block run_deps %}
{{super()}}
bin/ip/route2
{% endblock %}

{% block go_url %}
https://github.com/ProtonVPN/wireguard-go/archive/8338bafb983efb9c2541eb5b68537fccdb204654.tar.gz
{% endblock %}

{% block go_sha %}
448f01e134c879d226ccc8bbcbe8bb41890b5130a29ff43b2f62ee5a9b93df26
{% endblock %}

{% block step_setup %}
{{super()}}
export CGO_ENABLED=0
{% endblock %}

{% block unpack %}
{{super()}}
mkdir -p cmd/proton-stealth
base64 -d << EOF > cmd/proton-stealth/main.go
{% include 'main.go/base64' %}
EOF
base64 -d << EOF > cmd/proton-stealth/main_test.go
{% include 'main_test.go/base64' %}
EOF
base64 -d << EOF > cmd/proton-stealth/live_test.go
{% include 'live_test.go/base64' %}
EOF
base64 -d << EOF > cmd/proton-stealth/socks.go
{% include 'socks.go/base64' %}
EOF
base64 -d << EOF > cmd/proton-stealth/namespace.go
{% include 'namespace.go/base64' %}
EOF
base64 -d << EOF > cmd/proton-stealth/socks_test.go
{% include 'socks_test.go/base64' %}
EOF
{% endblock %}

{% block patch %}
# Proton's UDP bind references these methods on Linux, but upstream only
# includes them on Android. The implementations also work on regular Linux.
cp conn/boundif_android.go conn/boundif_linux.go
# Receive returns a pointer endpoint whereas ParseEndpoint returns a value.
# WireGuard roaming updates the peer after the handshake; compare addresses.
base64 -d << EOF | patch -p1
{% include 'transport.patch/base64' %}
EOF
{% endblock %}

{% block go_build_flags %}
{{super()}}
-o=proton-stealth
./cmd/proton-stealth
{% endblock %}

{% block test %}
go test -mod=vendor -timeout=60s ./cmd/proton-stealth
{% endblock %}

{% block go_bins %}
proton-stealth
{% endblock %}

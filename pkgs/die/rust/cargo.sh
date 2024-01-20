{% extends '//die/c/ix.sh' %}

{% block std_box %}
bld/rust
bld/python
bld/stable/unpack
{{super()}}
{% endblock %}

{% block unpack %}
mkdir src
cd src
stable_unpack ${src}/*lz4
{% endblock %}

{% block cargo_refine %}
{% endblock %}

{% block bld_data %}
aux/cargo(url={{self.cargo_url().strip()}},sha={{self.cargo_sha().strip()}},parent_id={{self.cargo_sha().strip()}},refine={{self.cargo_refine().strip() | b64e}})
{% endblock %}

{% block host_libs %}
lib/shim/fake(lib_name=gcc_s)
{% endblock %}

{% block setup_host_flags %}
export LDFLAGS="-L${LD_LIBRARY_PATH} ${LDFLAGS}"
{% endblock %}

{% block setup %}
export CARGO_BUILD_JOBS=8
export CARGO_INSTALL_ROOT=${out}
export CARGO_HOME=${PWD}/vendored
{% endblock %}

{% block setup_tools %}
export TARGET_CC=$(which cc)

cat << EOF > cc
#!/usr/bin/env python3

import sys
import subprocess

target_cc="${TARGET_CC}"
host_cc="${HOST_CC}"

def flt_target(cmd):
    for x in cmd:
        if 'self-contained' in x and '.o' in x:
            continue
        elif 'self-contained' in x:
            yield '/nowhere'
        elif '-Wl,' in x:
            continue
        elif '-lunwind' in x:
            continue
        elif x == '-static-pie':
            continue
        else:
            yield x

def flt_host(cmd):
    return cmd

if '--no' in str(sys.argv):
    cc = host_cc
else:
    cc = target_cc

try:
    subprocess.check_call([cc] + sys.argv[1:])
except:
    subprocess.check_call(list(flt_target([cc] + sys.argv[1:])))
EOF

cp cc c++

chmod +x cc c++
{% endblock %}

{% set cargo_options %}
{% block cargo_options %}
{% endblock %}
{% endset %}

{% block build %}
export HOST_CXX=$(which c++)
export HOST_CC=$(which cc)
cargo build --locked --offline --release {{ix.fix_list(cargo_options)}}
{% endblock %}

{% block install %}
cargo install --locked --offline --release
{% endblock %}

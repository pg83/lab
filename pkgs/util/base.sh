{% extends '//util/sh.sh' %}

{% block shscript %}
step_unpack() {
echo 'unpack step'

{% block preunpack%}
{% endblock %}

{% block unpack %}
{% endblock %}

{% block postunpack%}
{% endblock %}
}

step_patch() {
echo 'patch step'

{% block prepatch %}
{% endblock %}

{% block patch %}
{% endblock %}

{% block postpatch %}
{% endblock %}
}

step_configure() {
echo 'configure stage'

{% block cflags %}
{% endblock %}

{% block preconf %}
{% endblock %}

{% block configure %}
{% endblock %}

{% block postconf %}
{% endblock %}
}

step_build() {
echo 'build stage'

{% block prebuild %}
{% endblock %}

{% block build %}
{% endblock %}

{% block postbuild%}
{% endblock %}
}

step_test() {
echo 'test stage'

{% block pretest%}
{% endblock %}

{% block test %}
{% endblock %}

{% block posttest %}
{% endblock %}
}

step_install() {
echo 'install stage'

{% block preinstall%}
{% endblock %}

{% block install %}
{% endblock %}

{% block postinstall%}
{% endblock %}

cat << EOF > ${out}/env
{% block env %}
{% endblock %}
EOF
}

do_unpack() {
    step_unpack
}

do_patch() {
    do_unpack && (step_patch)
}

do_configure() {
    do_patch && step_configure
}

do_build() {
    do_configure && (step_build)
}

do_install() {
    do_build && (step_install)
}

do_test() {
    do_install && (step_test)
}

do_execute() {
    echo "execute ${out}"
    do_test
    echo "done ${out}"
}

(do_execute)
{% endblock %}

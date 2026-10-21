{% extends '//die/go/build.sh' %}

{% block go_url %}
https://github.com/pg83/wirez/archive/refs/tags/9.tar.gz
{% endblock %}

{% block go_sha %}
ea7263771f613463b57666a89dda600fe5ac0eb3ed043c514a142fa30e4087b6
{% endblock %}

{% block patch %}
grep -q 'privileged := isInitialUserNamespaceRoot()' run.go
sed -i 's/privileged := isInitialUserNamespaceRoot()/privileged := os.Geteuid() == 0/' run.go
grep -q 'if \*privileged {' run_container.go
sed -i 's/if \*privileged {/if *privileged \&\& (*uid != os.Geteuid() || *gid != os.Getegid()) {/' run_container.go
{% endblock %}

{% block go_bins %}
wirez
{% endblock %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

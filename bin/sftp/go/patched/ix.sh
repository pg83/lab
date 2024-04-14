{% extends '//bin/sftp/go/unwrap/ix.sh' %}

{% block patch %}
{{super()}}
sed -e 's|func setConfigFile(|func setConfigFileXXX(|' \
    -i internal/config/config.go
cat << EOF >> internal/config/config.go
func setConfigFile(configDir, configFile string) {
    setConfigFileXXX(configDir, configFile)
    viper.SetConfigType("json")
}
EOF
{% endblock %}

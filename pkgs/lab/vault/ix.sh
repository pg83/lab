{% extends '//die/hub.sh' %}

{% block pubkey %}
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDZvPrN52SQSe5Xh4lqatDvx0yUftwtY0NZZ5FdAfnYa+QeZRnsxvAHq2RsFb32zl3SHPcuvaaE1yPNzRTuQivf56URCZ82xyIVmd/5DlU/7lZzJHiPnmaVvE2oJFdynOYsQcMZEnoXNpspA0hOx3b7I9Td6Zd/gJrushgZ0j7t28eztWXJaysGCg5kM5bGRNuJTUxk8Ql9Ag+CESJTg/7Ka98RzWyWHc8WLBtCLyfB+885cuiCeULLBUVk2JVIReIi8fs3Lhbwe6GFQfny9hEjJRNQyvUL4ibw0Sh1r7+mXwzo9uryt0AG1tOvo9hVQV8FksRhr6d5MZk3aLDmw7gxXz/Wh0s9DMtsE6ONPATK6NGWrbrO4paU8hClxz80E7uEQ/wM9LPrxspuSGYHrZQapsoJag173MhR9ChixEIXcs4ZVAZKJ9BhyH9e9U1GGUe5qbWgdA6Ve4kxSSvs2l6M1HzvEGrN8mmnktXcNZrTS6+V69Klwtdx7g4wWb/k5vU= pg@stalix
{% endblock %}

{% block run_deps %}
lab/vault/scripts
etc/user/0(hash=x,pubkey={{self.pubkey().strip()}},user=pg)
etc/services/runit(srv_dir=vault,srv_command=exec vault_cycle)
{% endblock %}

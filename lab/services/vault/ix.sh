{% extends '//die/hub.sh' %}

{% block pubkey1 %}
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDZvPrN52SQSe5Xh4lqatDvx0yUftwtY0NZZ5FdAfnYa+QeZRnsxvAHq2RsFb32zl3SHPcuvaaE1yPNzRTuQivf56URCZ82xyIVmd/5DlU/7lZzJHiPnmaVvE2oJFdynOYsQcMZEnoXNpspA0hOx3b7I9Td6Zd/gJrushgZ0j7t28eztWXJaysGCg5kM5bGRNuJTUxk8Ql9Ag+CESJTg/7Ka98RzWyWHc8WLBtCLyfB+885cuiCeULLBUVk2JVIReIi8fs3Lhbwe6GFQfny9hEjJRNQyvUL4ibw0Sh1r7+mXwzo9uryt0AG1tOvo9hVQV8FksRhr6d5MZk3aLDmw7gxXz/Wh0s9DMtsE6ONPATK6NGWrbrO4paU8hClxz80E7uEQ/wM9LPrxspuSGYHrZQapsoJag173MhR9ChixEIXcs4ZVAZKJ9BhyH9e9U1GGUe5qbWgdA6Ve4kxSSvs2l6M1HzvEGrN8mmnktXcNZrTS6+V69Klwtdx7g4wWb/k5vU= pg@stalix
{% endblock %}

{% block pubkey2 %}
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCuKaiTEbzhjmgRUlg3DwyrSNRAD6NgW1UAEkrQbe0BY+QxzEmazKcJFy1gXbcZQaa/kSZSpeRBSxIhTY5jRMmW+e2KaSJ2Y0YwvAxgpx22MOalLDP4emRWM+CbTK0UoD61z5AQLsbteZxMfYKvFx3+5yt91qjcmUJ3lABiN2eCYri8RV1ODFliOB3ObAf4wrSWsnXQRxZaX5EVEjBu84Ec5nluLcJL7Ybo3h91H2AcqPwmhQd57XRCP3lV/8xTSU9rOr803iqiDO4zDF2x7zdMBlBFdwV+r92UXhpvFfV9G2sxsY94N4BdrmKi0VYktFETbr0RpVo14VhP6yg8YrkjRZQhoBeUI+DUBVPuutYy78xhDKu3H0ds9/f0Uf3wrf1UF1UzT7YRB6KHB5dvQIgiCDRM5Zt+x52pv5FsIabCrXGB4XzGsqmXeqKPOsSpKNBaDIWYImyDDc/6N5XtFyy4x+PcAln2vNTUlKsdkRkFAG03PI1UGRGVqyeQ1UfIle8= pg@pg-osx
{% endblock %}

{% block run_deps %}
bin/dropbear/runit
lab/services/vault/scripts
etc/services/runit(srv_dir=vault,srv_command=exec vault_cycle)
etc/user(hash=x,pubkey={{self.pubkey1().strip()}},user=pg,login_shell=/bin/sh,userid=10000)
etc/user(hash=x,pubkey={{self.pubkey2().strip()}},user=pgx,login_shell=/bin/sh,userid=10001)
{% endblock %}

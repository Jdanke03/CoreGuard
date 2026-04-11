import ssl
from django.core.mail.backends.smtp import EmailBackend


class UnsafeEmailBackend(EmailBackend):
    """Dev-only SMTP backend that disables SSL cert verification."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local_hostname = getattr(self, "local_hostname", None)

    def _get_ssl_context(self):
        return ssl._create_unverified_context()

    def open(self):
        if self.connection:
            return False

        try:
            if self.use_ssl:
                self.connection = self.connection_class(
                    self.host,
                    self.port,
                    local_hostname=self.local_hostname,
                    timeout=self.timeout,
                    context=self._get_ssl_context(),
                )
            else:
                self.connection = self.connection_class(
                    self.host,
                    self.port,
                    local_hostname=self.local_hostname,
                    timeout=self.timeout,
                )
            if self.use_tls:
                self.connection.starttls(context=self._get_ssl_context())
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except Exception:
            if not self.fail_silently:
                raise
            return False

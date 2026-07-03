class IntegrityResult:
    def __init__(self, code, severity, message, obj=None, suggestion=None):
        self.code = code
        self.severity = severity
        self.message = message
        self.obj = obj
        self.suggestion = suggestion

    def to_dict(self):
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object": str(self.obj) if self.obj else None,
            "suggestion": self.suggestion,
        }


class IntegrityRule:
    code = "BASE"
    severity = "INFO"
    description = ""

    def check(self, prescription):
        return []

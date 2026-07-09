class IntegrityResult:
    def __init__(
        self,
        code,
        severity,
        message,
        obj=None,
        suggestion=None,
        title=None,
        category=None,
        description=None,
        solution=None,
        autofix=False,
    ):
        self.code = code
        self.severity = severity
        self.message = message
        self.obj = obj
        self.suggestion = suggestion
        self.title = title
        self.category = category
        self.description = description
        self.solution = solution
        self.autofix = autofix

    def to_dict(self):
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object": str(self.obj) if self.obj else None,
            "suggestion": self.suggestion,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "solution": self.solution,
            "autofix": self.autofix,
        }


class IntegrityRule:
    code = "BASE"
    severity = "INFO"
    title = ""
    category = "Général"
    description = ""
    solution = ""
    autofix = False
    explain = True

    def result(self, message, obj=None, suggestion=None):
        return IntegrityResult(
            code=self.code,
            severity=self.severity,
            message=message,
            obj=obj,
            suggestion=suggestion or self.solution,
            title=self.title,
            category=self.category,
            description=self.description,
            solution=self.solution,
            autofix=self.autofix,
        )

    def check(self, context):
        return []

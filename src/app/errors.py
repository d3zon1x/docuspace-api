class PasswordsDoNotMatchError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


class NoAccessError(Exception):
    pass


class OwnerRequiredError(Exception):
    pass


class AlreadyProjectMemberError(Exception):
    pass


class DocumentNotFoundError(Exception):
    pass


class DocumentAlreadyExistsError(Exception):
    pass


class EmptyUploadError(Exception):
    pass


class DuplicateFilenameError(Exception):
    pass


class UnsupportedFileTypeError(Exception):
    pass


class QuotaExceededError(Exception):
    pass

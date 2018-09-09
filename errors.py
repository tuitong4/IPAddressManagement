class IPAMError(Exception):
    pass

class IPAMValueError(IPAMError):
    pass

class IPAMInvalidValueTypeError(IPAMValueError):
    pass

class IPAMDatabaseError(IPAMError):
    pass

class IPAMDatabaseNonExistentError(IPAMDatabaseError):
    pass


class IPAMDuplicateError(IPAMDatabaseError):
    pass

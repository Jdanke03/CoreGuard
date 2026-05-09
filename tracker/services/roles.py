PHYSIO_GROUP_NAME = "Physio"


def is_physio(user):
    return user.is_authenticated and user.groups.filter(name=PHYSIO_GROUP_NAME).exists()


def is_not_physio(user):
    return not user.groups.filter(name=PHYSIO_GROUP_NAME).exists()

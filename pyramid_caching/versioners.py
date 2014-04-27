import inspect

from zope.interface import implementer

from pyramid_caching.interfaces import (
    IIdentityInspector,
    IKeyVersioner,
    IModelVersioner,
    )


def includeme(config):
    registry = config.registry

    def identify(model_obj_or_cls):
        return registry.queryAdapter(model_obj_or_cls, IIdentityInspector)

    key_versioner = MemoryKeyVersioner()

    model_versioner = ModelVersioner(key_versioner, identify)

    config.registry.registerUtility(model_versioner)
    config.add_directive('get_model_versioner', get_model_versioner)


def get_model_versioner(config):
    return config.registry.getUtility(IModelVersioner)


@implementer(IKeyVersioner)
class MemoryKeyVersioner(object):
    """Highly inefficient in-memory key store as a proof of concept.
    It can be used in tests.

    Do not use in production.
    """

    def __init__(self):
        self.versions = dict()

    def _format(self, key):
        return 'version.%s' % key

    def get(self, key, default=0):
        return self.versions.get(self._format(key), default)

    def get_multi(self, keys, default=0):
        return [self.get(key, default) for key in keys]

    def incr(self, key, start=0):
        k = self._format(key)
        version = self.versions.get(k, start) + 1
        self.versions[k] = version


@implementer(IModelVersioner)
class ModelVersioner(object):

    def __init__(self, key_versioner, identify):
        self.key_versioner = key_versioner
        self.identify = identify

    def get_key(self, obj_or_cls):
        identity = self.identify(obj_or_cls)
        return '%s:v=%s' % (identity, self.key_versioner.get(identity))

    def get_multi_keys(self, objects_or_classes):
        keys = [self.identify(obj_or_cls)
                for obj_or_cls in objects_or_classes]

        versions = self.key_versioner.get_multi(keys)

        return ['%s:v=%s' % (key, version)
                for (key, version) in zip(keys, versions)]

    def incr(self, obj_or_cls, start=0):
        self.key_versioner.incr(self.identify(obj_or_cls))

        if not inspect.isclass(obj_or_cls):  # increment model class version
            identity = self.identify(obj_or_cls.__class__)
            self.key_versioner.incr(identity)

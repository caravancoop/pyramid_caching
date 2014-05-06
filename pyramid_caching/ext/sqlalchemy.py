from __future__ import absolute_import

import inspect
import logging

from zope.interface import implementer

from pyramid_caching.interfaces import IIdentityInspector

from sqlalchemy import event

log = logging.getLogger(__name__)


def includeme(config):

    config.add_directive('register_sqla_session_caching_hook',
                         register_sqla_session_caching_hook)

    config.add_directive('register_sqla_base_class',
                         register_sqla_base_class)

    identity_inspector = SqlAlchemyIdentityInspector()

    config.registry.registerUtility(identity_inspector,
                                    provided=IIdentityInspector)


def register_sqla_base_class(config, base_cls):
    registry = config.registry

    identity_inspector = registry.getUtility(IIdentityInspector)

    registry.registerAdapter(lambda _: identity_inspector, required=[base_cls],
                             provided=IIdentityInspector)

    registry.registerAdapter(lambda _: identity_inspector,
                             required=[base_cls.__class__],
                             provided=IIdentityInspector)


def register_sqla_session_caching_hook(config, session_cls):
    versioner = config.get_versioner()

    def on_before_commit(session):
        dirty = session.dirty
        deleted = session.deleted

        def incr_models(session):
            # XXX: should increment only cacheable models
            log.debug('incrementing dirty=%s deleted=%s', dirty, deleted)

            for model in dirty:
                versioner.incr(model)

            for model in deleted:
                versioner.incr(model)

        if dirty or deleted:
            event.listen(session, 'after_commit', incr_models)

    event.listen(session_cls, 'before_commit', on_before_commit)


@implementer(IIdentityInspector)
class SqlAlchemyIdentityInspector(object):

    def identify(self, obj_or_cls, ids_dict=None):
        tablename = obj_or_cls.__tablename__

        is_class = inspect.isclass(obj_or_cls)

        if is_class and ids_dict is None:
            return tablename

        ids = ''
        if ids_dict:
            ids += ':'.join(['%s=%s' % (k, v)
                             for k, v in ids_dict.iteritems()])

        # with a table user_message with a composite primary key user_id and id
        # an object user_message(user_id=123, id=456) will give:
        # 'user_message:user_id=123:id=456'

        if not is_class:
        # TODO: if table has no primary keys :-/
            table = obj_or_cls.__table__

            ids += ':'.join(
                ['%s=%s' % (col_name, getattr(obj_or_cls, col_name))
                 for col_name in table.primary_key.columns.keys()]
                )

        return '%s:%s' % (tablename, ids)

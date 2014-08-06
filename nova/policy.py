# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Policy Engine For Nova."""

import os.path

from oslo.config import cfg

from nova import exception
from nova.openstack.common import policy
from nova import utils
from nova.openstack.common import log as logging

LOG = logging.getLogger(__name__)


policy_opts = [
    cfg.StrOpt('policy_file',
               default='policy.json',
               help=_('JSON file representing policy')),
    cfg.StrOpt('policy_default_rule',
               default='default',
               help=_('Rule checked when requested rule is not found')),
    ]

CONF = cfg.CONF
CONF.register_opts(policy_opts)

_POLICY_PATH = None
_POLICY_CACHE = {}


def reset():
    global _POLICY_PATH
    global _POLICY_CACHE
    _POLICY_PATH = None
    _POLICY_CACHE = {}
    policy.reset()


def init():
    global _POLICY_PATH
    global _POLICY_CACHE
    if not _POLICY_PATH:
        _POLICY_PATH = CONF.policy_file
        if not os.path.exists(_POLICY_PATH):
            _POLICY_PATH = CONF.find_file(_POLICY_PATH)
        if not _POLICY_PATH:
            raise exception.ConfigNotFound(path=CONF.policy_file)
    utils.read_cached_file(_POLICY_PATH, _POLICY_CACHE,
                           reload_func=_set_rules)


def _set_rules(data):
    default_rule = CONF.policy_default_rule
    policy.set_rules(policy.Rules.load_json(data, default_rule))


def enforce(context, action, target, do_raise=True):
    """Verifies that the action is valid on the target in this context.

       :param context: nova context
       :param action: string representing the action to be checked
           this should be colon separated for clarity.
           i.e. ``compute:create_instance``,
           ``compute:attach_volume``,
           ``volume:attach_volume``
       :param target: dictionary representing the object of the action
           for object creation this should be a dictionary representing the
           location of the object e.g. ``{'project_id': context.project_id}``
       :param do_raise: if True (the default), raises PolicyNotAuthorized;
           if False, returns False

       :raises nova.exception.PolicyNotAuthorized: if verification fails
           and do_raise is True.

       :return: returns a non-False value (not necessarily "True") if
           authorized, and the exact value False if not authorized and
           do_raise is False.
    """
    init()

    credentials = context.to_dict()

    # Add the exception arguments if asked to do a raise
    extra = {}
    if do_raise:
        extra.update(exc=exception.PolicyNotAuthorized, action=action)

    return policy.check(action, target, credentials, **extra)


def check_is_admin(context):
    """Whether or not roles contains 'admin' role according to policy setting.

    """
    init()

    #the target is user-self
    credentials = context.to_dict()
    target = credentials

    return policy.check('context_is_admin', target, credentials)


@policy.register('is_admin')
class IsAdminCheck(policy.Check):
    """An explicit check for is_admin."""

    def __init__(self, kind, match):
        """Initialize the check."""

        self.expected = (match.lower() == 'true')

        super(IsAdminCheck, self).__init__(kind, str(self.expected))

    def __call__(self, target, creds):
        """Determine whether is_admin matches the requested value."""

        return creds['is_admin'] == self.expected


#NOTE: (schoksey): Extended functionality to support Field-based policy evaluations - start

def get_resource_and_action(action):
    """ Extract resource and action (write, read) from api operation """
    data = action.split(':', 1)[0].split('_', 1)
    return ("%ss" % data[-1], data[0] != 'get')

def _build_match_rule(action, target):
    """Create the rule to match for a given action.

    The policy rule to be matched is built in the following way:
    1) add entries for matching permission on objects
    2) add an entry for the specific action (e.g.: create_network)
    3) add an entry for attributes of a resource for which the action
       is being executed (e.g.: create_network:shared)

    """

    match_rule = policy.RuleCheck('rule', action)
    resource, is_write = get_resource_and_action(action)
    if is_write:
        if 'enforce_policy' in resource and is_write:
            attr_rule = policy.RuleCheck('rule', '%s:%s' % (action, resource))
            match_rule = policy.AndCheck([match_rule, attr_rule])

    return match_rule


@policy.register('field')
class FieldCheck(policy.Check):
    def __init__(self, kind, match):
	LOG.debug("SDC ************ __init__")
	LOG.debug("SDC ************ kind: %s", kind)
	LOG.debug("SDC ************ match: %s", match)
        # Process the match
        resource, field_value = match.split(':', 1)
        field, value = field_value.split('=', 1)

	LOG.debug("SDC ********* resource, field, value  - %s, %s, %s", resource, field, value)
        super(FieldCheck, self).__init__(kind, '%s:%s:%s' %
                                         (resource, field, value))

        self.field = field
        self.value = value

    def __call__(self, target_dict, cred_dict):
        target_value = target_dict.get(self.field)
        # target_value might be a boolean, explicitly compare with None
        if target_value is None:
            LOG.debug(_("Unable to find requested field: %(field)s in "
                        "target: %(target_dict)s"),
                      {'field': self.field,
                       'target_dict': target_dict})
            return False

        return target_value == self.value

def enforce_field(context, action, target):
    """Verifies that the action is valid on the target in this context.
    :param context: nova context
    :param action: string representing the action to be checked
        this should be colon separated for clarity.
    :param target: dictionary representing the object of the action
        for object creation this should be a dictionary representing the
        location of the object e.g. ``{'project_id': context.project_id}``

    :raises exceptions.Invalid: if verification fails.
    """
    init()
    LOG.debug("SDC ************ in enforce_feild")
    match_rule = _build_match_rule(action, target)
    credentials = context.to_dict()
    if not policy.check(match_rule, target, credentials, action=action):
	raise exception.InvalidInput(reason=("Rule violation: %(rule)s on : %(target)s", action, target))

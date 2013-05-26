# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
#    under the License
"""The Instance Group API Extension."""

import webob
from webob import exc

from nova.api.openstack import common
from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova.api.openstack import xmlutil
from nova.compute import instance_groups_api as api
import nova.exception
from nova.openstack.common import log as logging

LOG = logging.getLogger(__name__)

authorize = extensions.extension_authorizer('compute', 'instance_groups')

# TODO(senhuang) We need to add extension to nova's server API so that tenants
# could addInstanceGroup/removeInstanceGroup to/from a server.


def make_policy(elem):
    elem.set('name')


def make_member(elem):
    elem.set('instance_id')


def make_group(elem):
    elem.set('name')
    elem.set('id')
    policies = xmlutil.SubTemplateElement(elem, 'policies')
    policy = xmlutil.SubTemplateElement(policies, 'policy',
                                    selector='policies')
    make_policy(policy)
    members = xmlutil.SubTemplateElement(elem, 'members')
    member = xmlutil.SubTemplateElement(members, 'member',
                                    selector='members')
    make_member(member)
    elem.append(common.MetadataTemplate())


def make_group_brief(elem):
    elem.set('name')
    elem.set('id')

instance_group_nsmap = {None: xmlutil.XMLNS_V11, 'atom': xmlutil.XMLNS_ATOM}


def _authorize_context(req):
    context = req.environ['nova.context']
    authorize(context)
    return context


def get_policy_from_body(fn):
    """Makes sure that there is one policy in the request."""
    def wrapped(self, req, id, body, *args, **kwargs):
        if len(body) == 1 and "policy" in body:
            host = body['policy']
        else:
            raise exc.HTTPBadRequest()
        return fn(self, req, id, host, *args, **kwargs)
    return wrapped


class InstanceGroupTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('instance_group',
                                    selector='instance_group')
        make_group(root)
        return xmlutil.MasterTemplate(root, 1, nsmap=instance_group_nsmap)


class InstanceGroupsTemplate(xmlutil.TemplateBuilder):
    def construct(self):
        root = xmlutil.TemplateElement('instance_groups')
        elem = xmlutil.SubTemplateElement(root, 'instance_group',
                                        selector='instance_groups')
        # Note: listing instance groups only shows name and uuid
        make_group(elem)
        return xmlutil.MasterTemplate(root, 1, nsmap=instance_group_nsmap)


class InstanceGroupXMLDeserializer(wsgi.MetadataXMLDeserializer):
    """
    Deserializer to handle xml-formatted instance group requests.
    """

    metadata_deserializer = common.MetadataXMLDeserializer()

    def default(self, string):
        """Deserialize an xml-formatted instance group create request."""
        dom = xmlutil.safe_minidom_parse_string(string)
        instance_group = self._extract_instance_group(dom)
        return {'body': {'instance_group': instance_group}}

    def _extract_instance_group(self, node):
        """Marshal the instance attribute of a parsed request."""
        instance_group = {}
        ig_node = self.find_first_child_named(node, 'instance_group')
        if ig_node is not None:
            if ig_node.hasAttribute('name'):
                instance_group['name'] = ig_node.getAttribute('name')

            if ig_node.hasAttribute('id'):
                instance_group['id'] = ig_node.getAttribute('id')

            instance_group['policies'] = []
            policies = self._extract_policies(ig_node)
            if policies is not None:
                instance_group['policies'] = policies

            instance_group['metadata'] = {}
            meta_node = self.find_first_child_named(ig_node,
                                                    'metadata')
            if meta_node is not None:
                instance_group['metadata'] = self.extract_metadata(meta_node)

            instance_group['members'] = []
            members = self._extract_members(ig_node)
            if members is not None:
                instance_group['members'] = members
        return instance_group

    def _extract_policies(self, instance_group_node):
        """Marshal the instance group policies element of a parsed request."""
        policies_node = self.find_first_child_named(instance_group_node,
                                                'policies')
        if policies_node is not None:
            policy_nodes = self.find_children_named(policies_node,
                                                'policy')
            policies = []
            # [{'name': 'policy1'}, {'name': 'policy2'}, ...]
            if policy_nodes is not None:
                for node in policy_nodes:
                    policyDict = dict({'name': node.getAttribute('name')})
                    policies.append(policyDict)
            return policies

    def _extract_members(self, instance_group_node):
        """Marshal the instance group members element of a parsed request."""
        members_node = self.find_first_child_named(instance_group_node,
                                                   'members')
        if members_node is not None:
            member_nodes = self.find_children_named(members_node,
                                                'member')

            members = []
            # [{'instance_id': 'member1'}, {'instance_id': 'member2'}, ...]
            if member_nodes is not None:
                for node in member_nodes:
                    memberDict = dict({'instance_id':
                                    node.getAttribute('instance_id')})
                    members.append(memberDict)
            return members


class InstanceGroupActionXMLDeserializer(InstanceGroupXMLDeserializer):
    """
    Deserializer to handle xml-formatted instance group action requests.
    """

    def default(self, string):
        """Deserialize an xml-formatted instance group action request."""
        dom = xmlutil.safe_minidom_parse_string(string)
        actions = ['add_policies',
                   'remove_policies',
                   'add_members',
                   'remove_members',
                   'set_metadata']
        action = 'invalid_action'
        action_node = None
        for act in actions:
            node = self.find_first_child_named(dom, act)
            if node is not None:
                action = act
                action_node = node
                break

        action_body = {}
        if action.find('policies') > -1:
            action_body['policies'] = []
            policies = self._extract_policies(action_node)
            if policies is not None:
                action_body['policies'] = policies
        elif action.find('members') > -1:
            action_body['members'] = []
            members = self._extract_members(action_node)
            if members is not None:
                action_body['members'] = members
        elif action.find('metadata') > -1:
            meta_node = self.find_first_child_named(action_node, 'metadata')
            if meta_node is not None:
                action_body['metadata'] = self.extract_metadata(meta_node)
        return {'body': {action: action_body}}


class InstanceGroupControllerBase(wsgi.Controller):
    """Base class for Instance Group controllers."""

    def __init__(self):
        self.instance_group_api = api.InstanceGroupAPI()

    def _format_instance_group(self, context, group):
        instance_group = {}
        # the id field has its value as the uuid of the instance group
        # There is no 'uuid' key in instance_group seen by clients.
        # In addition, clients see policies as a list of {"name": "policy-1"}
        # dict; and they see members as a list of {"instance-id", "id"} dict.
        instance_group['id'] = group['uuid']
        instance_group['name'] = group['name']

        policies = []
        if group['policies'] is not None:
            for policy in group['policies']:
                policies.append(dict({'name': policy}))
        instance_group['policies'] = policies

        members = []
        if group['members'] is not None:
            instance_group['members'] = members
            for member in group['members']:
                members.append(dict({'instance_id': member}))
        instance_group['members'] = members

        metadata = {}
        if group['metadetails'] is not None:
            for k, v in group['metadetails'].items():
                metadata[k] = v
        instance_group['metadata'] = metadata
        return instance_group

    def _format_instance_group_brief(self, context, group):
        instance_group = {}
        # the id field has its value as the uuid of the instance group
        instance_group['id'] = group['uuid']
        instance_group['name'] = group['name']
        return instance_group

    def _from_body(self, body, key):
        if not body:
            raise exc.HTTPBadRequest()
        value = body.get(key, None)
        if value is None:
            raise exc.HTTPBadRequest()
        return value


class InstanceGroupController(InstanceGroupControllerBase):
    """The Instance group API controller for the OpenStack API."""

    @wsgi.serializers(xml=InstanceGroupTemplate)
    def show(self, req, id):
        """Return data about the given instance group."""
        context = _authorize_context(req)
        try:
            instance_group = self.instance_group_api.get(context, id)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        return {'instance_group': self._format_instance_group(context,
                                                              instance_group)}

    def delete(self, req, id):
        """Delete an instance group."""
        context = _authorize_context(req)
        try:
            self.instance_group_api.destroy(context, id)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        return webob.Response(status_int=202)

    @wsgi.serializers(xml=InstanceGroupsTemplate)
    def index(self, req):
        """Returns a list of instance groups."""
        context = _authorize_context(req)
        project_id = context.project_id
        raw_groups = self.instance_group_api.list(context,
                                                  project_id)

        limited_list = common.limited(raw_groups, req)
        result = [self._format_instance_group(context, group)
                    for group in limited_list]
        return {'instance_groups':
                list(sorted(result,
                            key=lambda k: (k['name'])))}

    @wsgi.serializers(xml=InstanceGroupTemplate)
    @wsgi.deserializers(xml=InstanceGroupXMLDeserializer)
    def create(self, req, body):
        """Creates a new instance group."""
        context = _authorize_context(req)
        vals = self._from_body(body, 'instance_group')
        policies = []
        inPolicies = vals.pop('policies', None)
        if inPolicies is not None:
            for policy in inPolicies:
                policies.append(policy['name'])

        members = []
        inMembers = vals.pop('members', None)
        if inMembers is not None:
            for member in inMembers:
                members.append(member['instance_id'])

        metadata = vals.pop('metadata', {})
        vals['project_id'] = context.project_id
        vals['user_id'] = context.user_id
        group_ref = self.instance_group_api.create_instance_group(context,
                                                vals,
                                                policies=policies,
                                                members=members,
                                                metadata=metadata)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}

    @wsgi.serializers(xml=InstanceGroupTemplate)
    @wsgi.deserializers(xml=InstanceGroupXMLDeserializer)
    def update(self, req, id, body):
        """Update an instance group's name, project_id, and user_id."""
        context = _authorize_context(req)

        instance_group_data = self._from_body(body, 'instance_group')
        # Need to do a copy since instance_group_data might contain a field
        # called "id", which will cause error if passed to update().
        # Also note the difference of the param list from create().
        vals = {}
        vals['name'] = instance_group_data.get('name', None)
        vals['project_id'] = context.project_id
        vals['user_id'] = context.user_id
        self.instance_group_api.update(context, id, vals)
        group_ref = self.instance_group_api.get(context, id)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}

    @wsgi.serializers(xml=InstanceGroupTemplate)
    @wsgi.deserializers(xml=InstanceGroupActionXMLDeserializer)
    def action(self, req, id, body):
        _actions = {
            'add_policies': self._add_policies,
            'remove_policies': self._remove_policies,
            'add_members': self._add_members,
            'remove_members': self._remove_members,
            'set_metadata': self._set_metadata
        }
        for action, data in body.iteritems():
            try:
                return _actions[action](req, id, data)
            except KeyError:
                msg = _('InstanceGroup does not have %s action') % action
                raise exc.HTTPBadRequest(explanation=msg)

        raise exc.HTTPBadRequest(explanation=_("Invalid request body"))

    def _add_policies(self, req, id, body):
        """Add policies to the specified instance group."""
        context = _authorize_context(req)
        inPolicies = self._from_body(body, 'policies')
        policies = []
        if inPolicies is not None:
            policies = [policy['name'] for policy in inPolicies]

        try:
            self.instance_group_api.add_policies(context,
                                                 id,
                                                 policies)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        group_ref = self.instance_group_api.get(context, id)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}

    def _remove_policies(self, req, id, body):
        """Removes policies from the specified instance group."""
        context = _authorize_context(req)
        inPolicies = self._from_body(body, 'policies')
        policies = []
        if inPolicies is not None:
            policies = [policy['name'] for policy in inPolicies]

        try:
            for policy in policies:
                self.instance_group_api.delete_policy(context,
                                                      id,
                                                      policy)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        except nova.exception.InstanceGroupPolicyNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        group_ref = self.instance_group_api.get(context, id)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}

    def _add_members(self, req, id, body):
        """Add members to the specified instance group."""
        context = _authorize_context(req)
        inMembers = self._from_body(body, 'members')
        members = []
        if inMembers is not None:
            members = [member['instance_id'] for member in inMembers]

        try:
            self.instance_group_api.add_members(context,
                                                id,
                                                members)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        group_ref = self.instance_group_api.get(context, id)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}

    def _remove_members(self, req, id, body):
        """Remove members from the specified instance group."""
        context = _authorize_context(req)
        inMembers = self._from_body(body, 'members')
        members = []
        if inMembers is not None:
            members = [member['instance_id'] for member in inMembers]
        try:
            for member in members:
                self.instance_group_api.delete_member(context,
                                                      id,
                                                      member)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        except nova.exception.InstanceGroupMemberNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        group_ref = self.instance_group_api.get(context, id)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}

    def _set_metadata(self, req, id, body):
        """Update metadata for the specified instance group."""
        context = _authorize_context(req)
        inMetadata = self._from_body(body, 'metadata')
        metadataToAdd = {}
        # Remove unneeded keys
        try:
            for key in inMetadata:
                # None is used to indicate the removal of a key
                if inMetadata[key] is None or inMetadata[key] == '':
                    self.instance_group_api.delete_metadata(context, id, key)
                else:
                    metadataToAdd[key] = inMetadata[key]
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        except nova.exception.InstanceGroupMetadataNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        # Add new key-value pairs and update existing keys with new values
        try:
            self.instance_group_api.add_metadata(context, id, metadataToAdd)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        group_ref = self.instance_group_api.get(context, id)
        return {'instance_group': self._format_instance_group(context,
                                                              group_ref)}


class InstanceGroupsTemplateElement(xmlutil.TemplateElement):
    def will_render(self, datum):
        return "instance_groups" in datum


class Instance_groups(extensions.ExtensionDescriptor):
    """Instance group support."""
    name = "InstanceGroups"
    alias = "os-instance-groups"
    namespace = ("http://docs.openstack.org/compute/ext/"
                 "instancegroups/api/v2.0")
    updated = "2013-06-20T00:00:00+00:00"

    def get_resources(self):
        resources = []

        res = extensions.ResourceExtension('os-instance-groups',
                                controller=InstanceGroupController(),
                                member_actions={"action": "POST", })

        resources.append(res)

        return resources

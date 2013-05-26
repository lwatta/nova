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

from lxml import etree
from oslo.config import cfg
import webob

from nova.api.openstack.compute.contrib import instance_groups
from nova.api.openstack import wsgi
import nova.db
from nova import exception
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import uuidutils
from nova import test
from nova.tests.api.openstack import fakes
from nova.tests import utils


CONF = cfg.CONF
LOG = logging.getLogger(__name__)

FAKE_UUID1 = 'a47ae74e-ab08-447f-8eee-ffd43fc46c16'
FAKE_UUID2 = 'c6e6430a-6563-4efa-9542-5e93c9e97d18'
FAKE_UUID3 = 'b8713410-9ba3-e913-901b-13410ca90121'


class AttrDict(dict):
    def __getattr__(self, k):
        return self[k]


def instance_group_template(**kwargs):
    igroup = kwargs.copy()
    igroup.setdefault('name', 'test')
    return igroup


def instance_group_resp_template(**kwargs):
    igroup = kwargs.copy()
    igroup.setdefault('name', 'test')
    igroup.setdefault('policies', [])
    igroup.setdefault('members', [])
    igroup.setdefault('metadata', {})
    return igroup


def instance_group_db(ig):
    attrs = ig.copy()
    if 'id' in attrs:
        attrs['uuid'] = attrs.pop('id')
    if 'policies' in attrs:
        policies = attrs.pop('policies')
        attrs['policies'] = [policy['name'] for policy in policies]
    if 'members' in attrs:
        members = attrs.pop('members')
        attrs['members'] = [member['instance_id'] for member in members]
    if 'metadata' in attrs:
        attrs['metadetails'] = attrs.pop('metadata')
    return AttrDict(attrs)


class InstanceGroupTest(test.TestCase):
    def setUp(self):
        super(InstanceGroupTest, self).setUp()
        self.controller = instance_groups.InstanceGroupController()
        self.app = fakes.wsgi_app(init_only=('os-instance-groups',))

    def test_create_instance_group(self):
        igroup = instance_group_template()

        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        res_dict = self.controller.create(req, {'instance_group': igroup})
        self.assertEqual(res_dict['instance_group']['name'], 'test')
        group_id = res_dict['instance_group']['id']
        self.assertTrue(uuidutils.is_uuid_like(group_id))
        self.assertEqual(res_dict['instance_group']['policies'], [])
        self.assertEqual(res_dict['instance_group']['members'], [])
        self.assertEqual(res_dict['instance_group']['metadata'], {})

    def test_create_instance_group_with_polcies_members_meta(self):
        igroup = instance_group_template()
        policies = [{'name': 'anti-affinity'}]
        igroup['policies'] = policies
        members = [{'instance_id': 'xx1'}, {'instance_id': 'xx2'}]
        igroup['members'] = members
        metadata = {'key1': 'value1'}
        igroup['metadata'] = metadata
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        res_dict = self.controller.create(req, {'instance_group': igroup})
        self.assertEqual(res_dict['instance_group']['name'], 'test')
        group_id = res_dict['instance_group']['id']
        self.assertTrue(uuidutils.is_uuid_like(group_id))
        self.assertEqual(res_dict['instance_group']['policies'], policies)
        self.assertEqual(res_dict['instance_group']['members'], members)
        self.assertEqual(res_dict['instance_group']['metadata'], metadata)

    def test_create_instance_group_with_ilegal_name(self):
        # blank name
        igroup = instance_group_template(name='')
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        self.assertRaises(exception.InvalidInput, self.controller.create,
                          req, {'instance_group': igroup})

        # name with length 256
        igroup = instance_group_template(name='1234567890' * 26)
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        self.assertRaises(exception.InvalidInput, self.controller.create,
                          req, {'instance_group': igroup})

        # non-string name
        igroup = instance_group_template(name=12)
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        self.assertRaises(exception.InvalidInput, self.controller.create,
                          req, {'instance_group': igroup})

    def test_create_instance_group_with_no_body(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create, req, None)

    def test_create_instance_group_with_no_instance_group(self):
        body = {'no-instanceGroup': None}

        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.create, req, body)

    def test_list_instance_group_by_tenant(self):
        groups = []
        policies = [{'name': 'anti-affinity'}]
        members = [{'instance_id': '1'}, {'instance_id': '2'}]
        metadata = {'key1': 'value1'}
        names = ['default-x', 'test']
        ig1 = instance_group_resp_template(id=str(1345),
                                           name=names[0],
                                           policies=policies,
                                           members=members,
                                           metadata=metadata)
        ig2 = instance_group_resp_template(id=str(891),
                                           name=names[1],
                                           policies=policies,
                                           members=members,
                                           metadata=metadata)

        groups = [ig1, ig2]
        expected = {'instance_groups': groups}

        def return_instance_groups(context, project_id):
            return [instance_group_db(ig) for ig in groups]

        self.stubs.Set(nova.db, 'instance_group_get_all_by_project_id',
                       return_instance_groups)

        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        res_dict = self.controller.index(req)
        self.assertEquals(res_dict, expected)

    def test_list_instance_group_all(self):
        all_groups = []
        tenant_groups = []
        policies = [{'name': 'anti-affinity'}]
        members = [{'instance_id': '1'}, {'instance_id': '2'}]
        metadata = {'key1': 'value1'}
        names = ['default-x', 'test']
        ig1 = instance_group_resp_template(id=str(1345),
                                           name=names[0],
                                           policies=[],
                                           members=members,
                                           metadata=metadata)
        ig2 = instance_group_resp_template(id=str(891),
                                           name=names[1],
                                           policies=policies,
                                           members=members,
                                           metadata={})
        tenant_groups = [ig2]
        all_groups = [ig1, ig2]

        all = {'instance_groups': all_groups}
        tenant_specific = {'instance_groups': tenant_groups}

        def return_all_instance_groups(context):
            return [instance_group_db(ig) for ig in all_groups]

        self.stubs.Set(nova.db, 'instance_group_get_all',
                       return_all_instance_groups)

        def return_tenant_instance_groups(context, project_id):
            return [instance_group_db(ig) for ig in tenant_groups]

        self.stubs.Set(nova.db, 'instance_group_get_all_by_project_id',
                       return_tenant_instance_groups)

        path = '/v2/fake/os-instance-groups'

        req = fakes.HTTPRequest.blank(path, use_admin_context=True)
        res_dict = self.controller.index(req)
        self.assertEquals(res_dict, all)
        req = fakes.HTTPRequest.blank(path)
        res_dict = self.controller.index(req)
        self.assertEquals(res_dict, tenant_specific)

    def test_delete_instance_group_by_id(self):
        ig = instance_group_template(id='123')

        self.called = False

        def instance_group_delete(context, id):
            self.called = True

        def return_instance_group(context, group_id):
            self.assertEquals(ig['id'], group_id)
            return instance_group_db(ig)

        self.stubs.Set(nova.db, 'instance_group_delete',
                       instance_group_delete)
        self.stubs.Set(nova.db, 'instance_group_get',
                       return_instance_group)

        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups/123')
        resp = self.controller.delete(req, '123')
        self.assertTrue(self.called)
        self.assertEqual(resp.status_int, 202)

    def test_delete_non_existing_instance_group(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups/invalid')
        self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                          req, 'invalid')

    def test_update_instance_groups(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')

        igroup = instance_group_template()
        newgroup = self.controller.create(req, {'instance_group': igroup})
        self.assertEqual(newgroup['instance_group']['name'], 'test')
        uuid = newgroup['instance_group']['id']
        # Now update the group
        igroup_update = instance_group_template()
        igroup_update['id'] = uuid
        # change the name
        igroup_update['name'] = 'update_name'
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups/' + uuid)
        req.method = 'PUT'
        body = {'instance_group': igroup_update}
        req.headers['content-type'] = 'application/json;charset=utf8'
        req.headers['accept'] = 'application/json'
        req.boby = jsonutils.dumps(body)
        res_dict = self.controller.update(req, uuid, body)
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   name='update_name')
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_add_policies(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        igroup = instance_group_template()
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # add policies
        policies = [{'name': 'anti-affinity'}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_policies': {'policies':
                                                              policies}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=policies)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add another list of policies
        policies2 = [{'name': 'different-rack'}]
        res_dict = self.controller.action(req, uuid,
                                          body={'add_policies': {'policies':
                                                              policies2}})
        comb_policies = policies + policies2
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=comb_policies)
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_add_duplicate_policies(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        igroup = instance_group_template()
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # add policies
        policies = [{'name': 'anti-affinity'}]
        res_dict = self.controller.action(req, uuid,
                                          body={'add_policies': {'policies':
                                                              policies}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=policies)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add another list of policies with duplicate policy as existing one
        policies2 = [{'name': 'anti-affinity'}, {'name': 'different-rack'}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_policies': {'policies':
                                                              policies2}})
        comb_policies = policies2
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=comb_policies)
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_remove_policies(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        policies = [{'name': 'anti-affinity'}]
        igroup = instance_group_template(policies=policies)
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # remove policies
        res_dict = self.controller.action(req, uuid,
                                          body={'remove_policies':
                                               {'policies': policies}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=[])
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add a list of policies
        policies2 = [{'name': 'anti-affinity'}, {'name': 'different-rack'}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_policies': {'policies':
                                                              policies2}})
        comb_policies = policies2
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=comb_policies)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # remove policies
        res_dict = self.controller.action(req, uuid,
                                          body={'remove_policies':
                                               {'policies': policies}})
        left_policies = [{'name': 'different-rack'}]
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   policies=left_policies)
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_add_members(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')

        igroup = instance_group_template()
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # add members
        members = [{'instance_id': FAKE_UUID1}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_members': {'members':
                                                              members}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=members)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add another list of members
        members2 = [{'instance_id': FAKE_UUID2}, {'instance_id': FAKE_UUID3}]
        res_dict = self.controller.action(req, uuid,
                                          body={'add_members':
                                               {'members': members2}})
        comb_members = members + members2
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=comb_members)
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_add_duplicate_members(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')

        igroup = instance_group_template()
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # add members
        members = [{'instance_id': FAKE_UUID1}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_members': {'members':
                                                              members}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=members)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add another list of members with overlapping member
        members2 = [{'instance_id': FAKE_UUID1}, {'instance_id': FAKE_UUID2}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_members': {'members':
                                                              members2}})
        comb_members = members2
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=comb_members)
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_remove_members(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        members = [{'instance_id': FAKE_UUID1}]
        igroup = instance_group_template(members=members)
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # remove members
        res_dict = self.controller.action(req, uuid,
                                          body={'remove_members':
                                               {'members': members}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=[])
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add another list of members
        members2 = [{'instance_id': FAKE_UUID1}, {'instance_id': FAKE_UUID2}]
        res_dict = self.controller.action(req, uuid,
                                           body={'add_members':
                                                {'members': members2}})
        comb_members = members2
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=comb_members)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # remove members again
        res_dict = self.controller.action(req, uuid,
                                          body={'remove_members':
                                               {'members': members}})
        left_members = [{'instance_id': FAKE_UUID2}]
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   members=left_members)
        self.assertEqual(res_dict['instance_group'], igroup_resp)

    def test_set_metadata(self):
        req = fakes.HTTPRequest.blank('/v2/fake/os-instance-groups')
        igroup = instance_group_template()
        newgroup = self.controller.create(req, {'instance_group': igroup})
        uuid = newgroup['instance_group']['id']
        # add metadata
        metadata = {'key1': 'value1'}
        res_dict = self.controller.action(req, uuid,
                                          body={'set_metadata':
                                               {'metadata': metadata}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   metadata=metadata)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # add another metadata
        metadata2 = {'key2': 'value2'}
        res_dict = self.controller.action(req, uuid,
                                          body={'set_metadata':
                                               {'metadata': metadata2}})
        comb_metadata = {'key1': 'value1', 'key2': 'value2'}

        igroup_resp = instance_group_resp_template(id=uuid,
                                                   metadata=comb_metadata)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # remove one key
        metadata3 = {'key1': None}
        res_dict = self.controller.action(req, uuid,
                                          body={'set_metadata':
                                               {'metadata': metadata3}})
        left_metadata = {'key2': 'value2'}
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   metadata=left_metadata)
        self.assertEqual(res_dict['instance_group'], igroup_resp)
        # update one key and add another key
        metadata4 = {'key2': 'new_value2', 'key3': 'value3'}
        res_dict = self.controller.action(req, uuid,
                                          body={'set_metadata':
                                               {'metadata': metadata4}})
        igroup_resp = instance_group_resp_template(id=uuid,
                                                   metadata=metadata4)
        self.assertEqual(res_dict['instance_group'], igroup_resp)


class TestInstanceGroupXMLDeserializer(test.TestCase):

    def setUp(self):
        super(TestInstanceGroupXMLDeserializer, self).setUp()
        self.deserializer = instance_groups.InstanceGroupXMLDeserializer()

    def test_create_request(self):
        serial_request = """
<instance_group name="test">
</instance_group>"""
        request = self.deserializer.deserialize(serial_request)
        expected = {
            "instance_group": {
                "name": "test",
                "policies": [],
                "members": [],
                "metadata": {}
            },
        }
        self.assertEquals(request['body'], expected)

    def test_update_request(self):
        serial_request = """
<instance_group name="test">
<policies>
<policy name="policy-1"/>
<policy name="policy-2"/>
</policies>
<members>
<member instance_id="x"/>
</members>
<metadata>
<meta key="key1">value1</meta>
<meta key="key2">value2</meta>
</metadata>
</instance_group>"""
        request = self.deserializer.deserialize(serial_request)
        expected = {
            "instance_group": {
                "name": 'test',
                "policies": [{'name': 'policy-1'}, {'name': 'policy-2'}],
                "members": [{'instance_id': 'x'}],
                "metadata": {"key1": "value1", "key2": "value2"}
            },
        }
        self.assertEquals(request['body'], expected)

    def test_create_request_no_name(self):
        serial_request = """
<instance_group>
</instance_group>"""
        request = self.deserializer.deserialize(serial_request)
        expected = {
            "instance_group": {
            "members": [],
            "policies": [],
            "metadata": {}
            },
        }
        self.assertEquals(request['body'], expected)

    def test_corrupt_xml(self):
        """Should throw a 400 error on corrupt xml."""
        self.assertRaises(
                exception.MalformedRequestBody,
                self.deserializer.deserialize,
                utils.killer_xml_body())


class TestInstanceGroupXMLSerializer(test.TestCase):
    def setUp(self):
        super(TestInstanceGroupXMLSerializer, self).setUp()
        self.namespace = wsgi.XMLNS_V11
        self.index_serializer = instance_groups.InstanceGroupsTemplate()
        self.default_serializer = instance_groups.InstanceGroupTemplate()

    def _tag(self, elem):
        tagname = elem.tag
        self.assertEqual(tagname[0], '{')
        tmp = tagname.partition('}')
        namespace = tmp[0][1:]
        self.assertEqual(namespace, self.namespace)
        return tmp[2]

    def _verify_instance_group(self, raw_group, tree):
        policies = raw_group['policies']
        members = raw_group['members']
        metadata = raw_group['metadata']
        self.assertEqual('instance_group', self._tag(tree))
        self.assertEqual(raw_group['id'], tree.get('id'))
        self.assertEqual(raw_group['name'], tree.get('name'))
        self.assertEqual(3, len(tree))
        for child in tree:
            child_tag = self._tag(child)
            if child_tag == 'policies':
                self.assertEqual(len(policies), len(child))
                for idx, gr_child in enumerate(child):
                    self.assertEqual(self._tag(gr_child), 'policy')
                    self.assertEqual(policies[idx]['name'],
                                     gr_child.get('name'))
            elif child_tag == 'members':
                self.assertEqual(len(members), len(child))
                for idx, gr_child in enumerate(child):
                    self.assertEqual(self._tag(gr_child), 'member')
                    self.assertEqual(members[idx]['instance_id'],
                                     gr_child.get('instance_id'))
            elif child_tag == 'metadata':
                self.assertEqual(len(metadata), len(child))
                metas = {}
                for idx, gr_child in enumerate(child):
                    self.assertEqual(self._tag(gr_child), 'meta')
                    key = gr_child.get('key')
                    self.assertTrue(key in ['key1', 'key2'])
                    metas[key] = gr_child.text
                self.assertEqual(len(metas), len(metadata))
                for k in metadata:
                    self.assertEqual(metadata[k], metas[k])

    def _verify_instance_group_brief(self, raw_group, tree):
        self.assertEqual('instance_group', self._tag(tree))
        self.assertEqual(raw_group['id'], tree.get('id'))
        self.assertEqual(raw_group['name'], tree.get('name'))

    def test_group_serializer(self):
        policies = [{"name": "policy-1"}, {"name": "policy-2"}]
        members = [{"instance_id": "1"}, {"instance_id": "2"}]
        metadata = dict(key1="value1", key2="value2")
        raw_group = dict(
            id='890',
            name='name',
            policies=policies,
            members=members,
            metadata=metadata)
        ig_group = dict(instance_group=raw_group)
        text = self.default_serializer.serialize(ig_group)

        tree = etree.fromstring(text)

        self._verify_instance_group(raw_group, tree)

    def test_groups_serializer(self):
        policies = [{"name": "policy-1"}, {"name": "policy-2"},
                    {"name": "policy-3"}]
        members = [{"instance_id": "1"}, {"instance_id": "2"},
                   {"instance_id": "3"}]
        metadata = dict(key1="value1", key2="value2")
        groups = [dict(
                 id='890',
                 name='test',
                 policies=policies[0:2],
                 members=members[0:2],
                 metadata=metadata),
                 dict(
                 id='123',
                 name='default',
                 policies=policies[2:],
                 members=members[2:],
                 metadata=metadata)]
        ig_groups = dict(instance_groups=groups)
        text = self.index_serializer.serialize(ig_groups)

        tree = etree.fromstring(text)

        self.assertEqual('instance_groups', self._tag(tree))
        self.assertEqual(len(groups), len(tree))
        for idx, child in enumerate(tree):
            self._verify_instance_group_brief(groups[idx], child)

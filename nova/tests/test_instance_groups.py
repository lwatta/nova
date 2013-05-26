# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
#    Copyright 2013 OpenStack Foundation
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

"""
Unit Tests for instance group code
"""

from nova.compute import instance_groups_api as api
from nova import context
from nova.db.sqlalchemy import models
from nova import exception
from nova.openstack.common import uuidutils
from nova import test


class InstanceGroupApiTestCase(test.TestCase):
    def setUp(self):
        super(InstanceGroupApiTestCase, self).setUp()
        self.user_id = 'fake_user'
        self.project_id = 'fake_project'
        self.context = context.RequestContext(self.user_id, self.project_id)
        self.instance_group_api = api.InstanceGroupAPI()

    def _get_default_values(self):
        return {'name': 'fake_name',
                'user_id': self.user_id,
                'project_id': self.project_id}

    def _create_instance_group(self, context, values, policies=[],
                               metadata={}, members=[]):
        return self.instance_group_api.create_instance_group(context,
                                                             values,
                                                             policies,
                                                             metadata,
                                                             members)

    def test_instance_group_create_no_key(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        self.assertEquals(result['name'], values['name'])
        self.assertEquals(result['user_id'], values['user_id'])
        self.assertEquals(result['project_id'], values['project_id'])
        self.assertTrue(uuidutils.is_uuid_like(result['uuid']))
        self.assertEquals(result['policies'], [])
        self.assertEquals(result['members'], [])
        metadata = result['metadetails']
        self.assertEquals(metadata, {})

    def test_instance_group_create_with_key(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        self.assertEquals(result['name'], values['name'])
        self.assertEquals(result['user_id'], values['user_id'])
        self.assertEquals(result['project_id'], values['project_id'])

    def test_instance_group_create_with_same_key(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        self.assertRaises(exception.InstanceGroupIdExists,
                          self._create_instance_group,
                          self.context,
                          values)

    def test_instance_group_get(self):
        values = self._get_default_values()
        result1 = self._create_instance_group(self.context, values)
        result2 = self.instance_group_api.get(self.context, result1['uuid'])
        self.assertEquals(result1['name'], result2['name'])
        self.assertEquals(result1['user_id'], result2['user_id'])
        self.assertEquals(result1['project_id'], result2['project_id'])
        self.assertEquals(result1['uuid'], result2['uuid'])

    def test_instance_group_destroy(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        self.instance_group_api.destroy(self.context, result['uuid'])
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.get,
                          self.context,
                          result['uuid'])

    def test_list(self):
        groups = self.instance_group_api.list(self.context)
        self.assertEquals(0, len(groups))
        value = self._get_default_values()
        result1 = self._create_instance_group(self.context, value)
        # list with valid project_id
        groups = self.instance_group_api.list(self.context,
                                              value['project_id'])
        self.assertEquals(1, len(groups))
        # list with invalid project_id
        groups = self.instance_group_api.list(self.context,
                                              'invalid_project_id')
        self.assertEquals(0, len(groups))
        # 2 instance groups created with different project_ids
        value2 = self._get_default_values()
        value2['project_id'] = 'new_project_id'
        result2 = self._create_instance_group(self.context, value2)
        groups = self.instance_group_api.list(self.context, 'fake_project')
        self.assertEquals(1, len(groups))
        groups = self.instance_group_api.list(self.context, 'new_project_id')
        self.assertEquals(1, len(groups))
        # admin can see all groups
        self.context = context.RequestContext(self.user_id,
                                              self.project_id,
                                              is_admin=True)
        groups = self.instance_group_api.list(self.context)
        self.assertEquals(2, len(groups))
        for group in groups:
            self.assertTrue(type(group) is models.InstanceGroup)
        results = [result1, result2]
        uuids1 = []
        for group in groups:
            uuids1.append(group['uuid'])
        uuids2 = []
        for result in results:
            uuids2.append(result['uuid'])
        self.assertEquals(set(uuids1), set(uuids2))

    def test_instance_group_update(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        group_uuid = result['uuid']
        values = self._get_default_values()
        values['name'] = 'new_fake_name'
        self.instance_group_api.update(self.context, group_uuid, values)
        result = self.instance_group_api.get(self.context, group_uuid)
        self.assertEquals(result['name'], 'new_fake_name')
        # update metadata
        values = self._get_default_values()
        metadataInput = {'key11': 'value1',
                         'key12': 'value2'}
        values['metadata'] = metadataInput
        self.instance_group_api.update(self.context, group_uuid, values)
        result = self.instance_group_api.get(self.context, group_uuid)
        metadata = result['metadetails']
        self.assertEquals(metadata['key11'], metadataInput['key11'])
        self.assertEquals(metadata['key12'], metadataInput['key12'])
        # update members
        values = self._get_default_values()
        members = ['instance_id1', 'instance_id2']
        values['members'] = members
        self.instance_group_api.update(self.context, group_uuid, values)
        result = self.instance_group_api.get(self.context, group_uuid)
        self.assertEquals(set(result['members']), set(members))
        # update policies
        values = self._get_default_values()
        policies = ['policy1', 'policy2']
        values['policies'] = policies
        self.instance_group_api.update(self.context, group_uuid, values)
        result = self.instance_group_api.get(self.context, group_uuid)
        self.assertEquals(set(result['policies']), set(policies))
        # test invalid ID
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.update, self.context,
                          'invalid_id', values)


class InstanceGroupMetadataApiTestCase(InstanceGroupApiTestCase):
    def test_instance_group_metadata_on_create(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        metadataInput = {'key11': 'value1',
                    'key12': 'value2'}
        result = self._create_instance_group(self.context, values,
                                             metadata=metadataInput)
        self.assertEquals(result['name'], values['name'])
        self.assertEquals(result['user_id'], values['user_id'])
        self.assertEquals(result['project_id'], values['project_id'])
        self.assertEquals(result['uuid'], values['uuid'])
        metadata = self.instance_group_api.get_metadata(self.context,
                                                        result['uuid'])
        self.assertEquals(set(metadata.keys()), set(metadataInput.keys()))
        for key in metadata.keys():
            metadata[key] = metadataInput[key]

    def test_instance_group_metadata_add(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        metadata = self.instance_group_api.add_metadata(self.context, id)
        self.assertEqual(metadata, {})
        metadataInput = {'key1': 'value1',
                    'key2': 'value2'}
        metadata2 = self.instance_group_api.add_metadata(self.context,
                                                         id,
                                                         metadataInput)
        self.assertEquals(set(metadata2.keys()), set(metadataInput.keys()))
        for key in metadata2.keys():
            metadata2[key] = metadataInput[key]
        # check add with existing keys
        metadataInput = {'key1': 'value1',
                    'key2': 'value2',
                    'key3': 'value3'}
        self.instance_group_api.add_metadata(self.context, id, metadataInput)
        metadata3 = self.instance_group_api.get_metadata(self.context, id)
        self.assertEquals(set(metadata3.keys()), set(metadataInput.keys()))
        for key in metadata3.keys():
            metadata3[key] = metadataInput[key]

    def test_instance_group_metadata_delete(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        metadataInput = {'key1': 'value1',
                    'key2': 'value2',
                    'key3': 'value3'}
        self.instance_group_api.add_metadata(self.context, id, metadataInput)
        metadata = self.instance_group_api.get_metadata(self.context, id)
        self.assertEquals(set(metadata.keys()), set(metadataInput.keys()))
        for key in metadata.keys():
            metadata[key] = metadataInput[key]
        self.instance_group_api.delete_metadata(self.context, id, 'key1')
        metadata = self.instance_group_api.get_metadata(self.context, id)
        self.assertTrue('key1' not in metadata)
        self.instance_group_api.delete_metadata(self.context, id, 'key2')
        metadata = self.instance_group_api.get_metadata(self.context, id)
        self.assertTrue('key2' not in metadata)

    def test_instance_group_metadata_delete_all(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        metadataInput = {'key1': 'value1',
                    'key2': 'value2',
                    'key3': 'value3'}
        self.instance_group_api.add_metadata(self.context, id, metadataInput)
        metadata = self.instance_group_api.get_metadata(self.context, id)
        self.assertEquals(set(metadata.keys()), set(metadataInput.keys()))
        for key in metadata.keys():
            metadata[key] = metadataInput[key]
        self.instance_group_api.delete_all_metadata(self.context, id)
        metadata = self.instance_group_api.get_metadata(self.context, id)
        self.assertEquals(metadata, {})

    def test_instance_group_metadata_invalid_ids(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.get_metadata,
                          self.context, 'invalid')
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.delete_metadata,
                          self.context,
                          'invalidid', 'key1')
        metadata = {'key1': 'value1',
                    'key2': 'value2'}
        self.instance_group_api.add_metadata(self.context, id, metadata)
        self.assertRaises(exception.InstanceGroupMetadataNotFound,
                          self.instance_group_api.delete_metadata,
                          self.context,
                          id,
                          'invalidkey')


class InstanceGroupMembersApiTestCase(InstanceGroupApiTestCase):
    def test_instance_group_members_on_create(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        membersInput = ['instance_id1', 'instance_id2']
        result = self._create_instance_group(self.context,
                                             values,
                                             members=membersInput)
        self.assertEquals(result['name'], values['name'])
        self.assertEquals(result['user_id'], values['user_id'])
        self.assertEquals(result['project_id'], values['project_id'])
        self.assertEquals(result['uuid'], values['uuid'])
        members = self.instance_group_api.get_members(self.context,
                                                      result['uuid'])
        self.assertEquals(set(members), set(membersInput))

    def test_instance_group_members_add(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values, members=[])
        id = result['uuid']
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(members, [])
        membersInput = ['instance_id1', 'instance_id2']
        self.instance_group_api.add_members(self.context, id, membersInput)
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(set(members), set(membersInput))
        # check membership add with overlapping instance ids
        membersInput2 = ['instance_id1', 'instance_id2', 'instance_id3']
        self.instance_group_api.add_members(self.context, id, membersInput2)
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(set(members), set(membersInput2))
        # check membership update without overlapping instance ids
        membersInput3 = ['instance_idx', 'instance_idy']
        self.instance_group_api.add_members(self.context, id, membersInput3)
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(set(members), set(membersInput2 + membersInput3))

    def test_instance_group_members_delete(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        membersInput = ['instance_id1', 'instance_id2', 'instance_id3']
        self.instance_group_api.add_members(self.context, id, membersInput)
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(set(members), set(membersInput))
        for instance_id in membersInput:
            self.instance_group_api.delete_member(self.context,
                                                  id,
                                                  instance_id)
            membersInput.remove(instance_id)
            members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(set(members), set(membersInput))

    def test_instance_group_members_delete_all(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        membersInput = ['instance_id1', 'instance_id2', 'instance_id3']
        self.instance_group_api.add_members(self.context, id, membersInput)
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(set(members), set(membersInput))
        self.instance_group_api.delete_all_members(self.context, id)
        members = self.instance_group_api.get_members(self.context, id)
        self.assertEquals(members, [])

    def test_instance_group_members_invalid_ids(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.get_members,
                          self.context, 'invalid')
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.delete_member,
                          self.context,
                          'invalidid',
                          'instance_id1')
        members = ['instance_id1', 'instance_id2']
        self.instance_group_api.add_members(self.context, id, members)
        self.assertRaises(exception.InstanceGroupMemberNotFound,
                          self.instance_group_api.delete_member,
                          self.context, id, 'invalid_id')


class InstanceGroupPoliciesApiTestCase(InstanceGroupApiTestCase):
    def test_instance_group_policies_on_create(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        policiesInput = ['policy1', 'policy2']
        result = self._create_instance_group(self.context, values,
                                             policies=policiesInput)
        self.assertEquals(result['name'], values['name'])
        self.assertEquals(result['user_id'], values['user_id'])
        self.assertEquals(result['project_id'], values['project_id'])
        self.assertEquals(result['uuid'], values['uuid'])
        policies = self.instance_group_api.get_policies(self.context,
                                                        result['uuid'])
        self.assertEquals(set(policies), set(policiesInput))

    def test_instance_group_policies_add(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(policies, [])
        policiesInput = ['policy1', 'policy2']
        self.instance_group_api.add_policies(self.context, id, policiesInput)
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(set(policies), set(policiesInput))
        # check adding policies with overlapping polices
        policiesInput2 = ['policy1', 'policy2', 'policy3']
        self.instance_group_api.add_policies(self.context, id, policiesInput2)
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(set(policies), set(policiesInput + policiesInput2))
        # check adding policies without overlapping polices
        policiesInput3 = ['policyx', 'policyy']
        self.instance_group_api.add_policies(self.context, id, policiesInput3)
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(set(policies), set(policiesInput2 + policiesInput3))

    def test_instance_group_policies_delete(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        policiesInput = ['policy1', 'policy2', 'policy3']
        self.instance_group_api.add_policies(self.context, id, policiesInput)
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(set(policies), set(policiesInput))
        for policy in policiesInput[:]:
            self.instance_group_api.delete_policy(self.context, id, policy)
            policiesInput.remove(policy)
            policies = self.instance_group_api.get_policies(self.context, id)
            self.assertEquals(set(policies), set(policiesInput))

    def test_instance_group_policies_delete_all(self):
        values = self._get_default_values()
        values['uuid'] = 'fake_id'
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        policiesInput = ['policy1', 'policy2', 'policy3']
        self.instance_group_api.add_policies(self.context, id, policiesInput)
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(set(policies), set(policiesInput))
        self.instance_group_api.delete_all_policies(self.context, id)
        policies = self.instance_group_api.get_policies(self.context, id)
        self.assertEquals(policies, [])

    def test_instance_group_policies_invalid_ids(self):
        values = self._get_default_values()
        result = self._create_instance_group(self.context, values)
        id = result['uuid']
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.get_policies,
                          self.context,
                          'invalid')
        self.assertRaises(exception.InstanceGroupNotFound,
                          self.instance_group_api.delete_policy,
                          self.context,
                          'invalidid',
                          'policy1')
        policies = ['policy1', 'policy2']
        self.instance_group_api.add_policies(self.context, id, policies)
        self.assertRaises(exception.InstanceGroupPolicyNotFound,
                          self.instance_group_api.delete_policy,
                          self.context, id, 'invalid_policy')

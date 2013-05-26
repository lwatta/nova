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

"""API Operations on Instance Groups."""

import re

import nova.db
from nova import exception
from nova.openstack.common import log as logging

from nova import utils

LOG = logging.getLogger(__name__)

INVALID_NAME_REGEX = re.compile("[^\w\.\- ]")

# [SH] Need to define a wrapper
INSTANCE_GROUP_API_DRIVER = 'nova.db'


class InstanceGroupAPI(nova.db.base.Base):
    """
    InstanceGroup API that manages instance groups
    """

    def __init__(self, **kwargs):
        super(InstanceGroupAPI, self).__init__(**kwargs)

    def validate_name(self, name):
        """
        Validate given instance group name.

        :param name:     the given name of the instance_group
        """
        # ensure name do not exceed 255 characters
        utils.check_string_length(name, 'name', min_length=1, max_length=255)

        # ensure name does not contain any special characters
        invalid_name = INVALID_NAME_REGEX.search(name)
        if invalid_name:
            msg = _("names can only contain [a-zA-Z0-9_.- ]")
            raise exception.InvalidInput(reason=msg)

    def create_instance_group(self, context, vals, policies=[],
                              metadata={}, members=[]):
        """Create an instance group

        :param vals: the parameter dictionary (name, and so on)
        :param policies: the list of policies to apply to this group
        :param metadata: extra key-value pair for this group
        :param members: the list of instances that are part of this group

        :returns: the newly created instance group object (with a UUID)
        :raises: InvalidInput, InstanceGroupIdExists
        """
        group_name = vals.get('name', None)
        if group_name is not None:
            self.validate_name(group_name)

        group_ref = nova.db.instance_group_create(context, vals, policies,
                                                  metadata, members)
        return group_ref

    def get(self, context, group_uuid=None):
        """Get the details of the given instance group_uuid
        raises: InstanceGroupNotFound
        """
        return nova.db.instance_group_get(context, group_uuid)

    def list(self, context, project_id=None):
        """List all groups."""
        if context.is_admin:
            groups = nova.db.instance_group_get_all(context)
        else:
            groups = nova.db.instance_group_get_all_by_project_id(context,
                                                              project_id)
        return groups

    def destroy(self, context, group_uuid):
        """Delete an instance group with the given group_uuid
        raises: InstanceGroupNotFound
        """
        nova.db.instance_group_delete(context, group_uuid)

    def update(self, context, group_uuid, values):
        """Update an instance group: replacing old values with new values
        raises: InstanceGroupNotFound
        """
        nova.db.instance_group_update(context, group_uuid, values)

    def add_metadata(self, context, group_uuid, metadata={}):
        """Add metadata to an instance group
        raises: InstanceGroupNotFound
        """
        return nova.db.instance_group_metadata_add(context,
                                                   group_uuid,
                                                   metadata)

    def delete_metadata(self, context, group_uuid, key):
        """Delete a key-value pair from the metadata of the instance group
        raises: InstanceGroupNotFound, InstanceGroupMetadataNotFound
        """
        if key is not None:
            nova.db.instance_group_metadata_delete(context, group_uuid, key)

    def delete_all_metadata(self, context, group_uuid):
        """Delete all key-value pairs from the metadata of the instance group
        raises: InstanceGroupNotFound
        """
        metadata = self.get_metadata(context, group_uuid)
        for key in metadata:
            self.delete_metadata(context, group_uuid, key)

    def get_metadata(self, context, group_uuid):
        return nova.db.instance_group_metadata_get(context, group_uuid)

    def add_members(self, context, group_uuid, members=[]):
        return nova.db.instance_group_members_add(context,
                                                  group_uuid,
                                                  members)

    def update_members(self, context, group_uuid, members):
        # [Todo]: do we need to support this operation?
        pass

    def delete_member(self, context, group_uuid, instance_id):
        """Delete an instance from the members of the instance group
        raises: InstanceGroupMemberNotFound
        """
        if instance_id is not None:
            nova.db.instance_group_member_delete(context,
                                                 group_uuid,
                                                 instance_id)

    def delete_all_members(self, context, group_uuid):
        members = self.get_members(context, group_uuid)
        for member in members:
            self.delete_member(context, group_uuid, member)

    def get_members(self, context, group_uuid):
        """Add members to an instance group
        raises: InstanceGroupNotFound
        """
        return nova.db.instance_group_members_get(context, group_uuid)

    def add_policies(self, context, group_uuid, policies):
        return nova.db.instance_group_policies_add(context,
                                                   group_uuid,
                                                   policies)

    def update_policies(self, context, group_uuid):
        # TODO(senhuang): need to support this operation
        pass

    def delete_policy(self, context, group_uuid, policy):
        """Delete a policy from the policies of the instance group
        raises: InstanceGroupPolicyNotFound
        """
        nova.db.instance_group_policy_delete(context, group_uuid, policy)

    def delete_all_policies(self, context, group_uuid):
        """Delete a policy from the policies of the instance group
        raises: InstanceGroupPolicyNotFound
        """
        policies = self.get_policies(context, group_uuid)
        if policies is not None:
            for policy in policies:
                self.delete_policy(context, group_uuid, policy)

    def get_policies(self, context, group_uuid):
        return nova.db.instance_group_policies_get(context, group_uuid)

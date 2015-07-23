from django.contrib.auth.models import User
from rest_framework import serializers

from onadata.apps.api import tools
from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.tools import get_organization_members
from onadata.apps.main.forms import RegistrationFormUserProfile
from onadata.libs.permissions import get_role_in_org
from onadata.libs.serializers.fields.json_field import JsonField
from onadata.apps.api.tools import _get_first_last_names


class OrganizationSerializer(serializers.HyperlinkedModelSerializer):
    org = serializers.WritableField(source='user.username')
    user = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    creator = serializers.HyperlinkedRelatedField(
        view_name='user-detail', lookup_field='username', read_only=True)
    users = serializers.SerializerMethodField('get_org_members')
    metadata = JsonField(source='metadata', required=False)

    class Meta:
        model = OrganizationProfile
        exclude = ('created_by', 'is_organization', 'organization')

    def restore_object(self, attrs, instance=None):
        if instance:
            # update the user model
            if 'name' in attrs:
                first_name, last_name = \
                    _get_first_last_names(attrs.get('name'))
                instance.user.first_name = first_name
                instance.user.last_name = last_name

                try:
                    instance.user.clean_fields(exclude=["password"])
                    instance.user.save()
                except ValidationError as e:
                    self.errors.update(e.message_dict)

            return super(OrganizationSerializer, self)\
                .restore_object(attrs, instance)

        org = attrs.get('user.username', None)
        org_name = attrs.get('name', None)
        org_exists = False
        creator = None

        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            pass
        else:
            self.errors['org'] = u'Organization %s already exists.' % org
            org_exists = True

        if 'request' in self.context:
            creator = self.context['request'].user

        if org and org_name and creator and not org_exists:
            attrs['organization'] = org_name
            orgprofile = tools.create_organization_object(org, creator, attrs)

            return orgprofile

        if not org:
            self.errors['org'] = u'org is required!'

        if not org_name:
            self.errors['name'] = u'name is required!'

        return attrs

    def validate_org(self, value):
        org = value.lower() if isinstance(value, basestring) else value
        if org in RegistrationFormUserProfile._reserved_usernames:
            raise serializers.ValidationError(
                u"%s is a reserved name, please choose another" % org)
        elif not RegistrationFormUserProfile.legal_usernames_re.search(org):
            raise serializers.ValidationError(
                u'organization may only contain alpha-numeric characters and '
                u'underscores')
        try:
            User.objects.get(username=org)
        except User.DoesNotExist:
            return org

        raise serializers.ValidationError(u'%s already exists' % org)

    def get_org_members(self, obj):
        members = get_organization_members(obj) if obj else []

        return [{
            'user': u.username,
            'role': get_role_in_org(u, obj),
            'first_name': u.first_name,
            'last_name': u.last_name,
            'gravatar': u.profile.gravatar,
            'metadata': u.profile.metadata,
        } for u in members]

import json

from django.test import RequestFactory
from django.contrib.contenttypes.models import ContentType

from onadata.apps.logger.models import OpenData, Instance
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.main.tests.test_base import TestBase


class TestOpenDataViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        self.view = OpenDataViewSet.as_view({
            'post': 'create',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve'
        })

    def test_create_open_data_object_with_valid_fields(self):
        request = self.factory.post('/', data={})
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            'Authentication credentials required.'
        )

        data = {
            'object_id': self.xform.id,
            'clazz': 'xform',
            'name': self.xform.id_string
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, 'Record was successfully created.')

    def test_create_open_data_object_with_invalid_fields(self):
        data = {
            'clazz': 'xform',
            'name': self.xform.id_string
        }

        data.update({'object_id': None})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            "{'object_id': [u'A valid integer is required.']}"
        )

        # check for xform with non-existent xform id (object_id)
        data.update({'object_id': 1000})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data.update({'invalid_key': 'invalid_value'})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            'Valid fields are object_id, clazz and name.'
        )

        data.pop('object_id')
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            'Fields object_id, clazz and name are required.'
        )

    def test_get_data_using_uuid(self):
        self._make_submissions()
        data = {
            'object_id': self.xform.id,
            'clazz': 'xform',
            'name': self.xform.id_string
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, 'Record was successfully created.')

        _open_data = OpenData.objects.last()
        uuid = _open_data.uuid
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_get_data_using_uuid_and_greater_than_query_param(self):
        self._make_submissions()
        data = {
            'object_id': self.xform.id,
            'clazz': 'xform',
            'name': self.xform.id_string
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, 'Record was successfully created.')

        first_instance = Instance.objects.first()
        _open_data = OpenData.objects.last()
        uuid = _open_data.uuid

        request = self.factory.get(
            '/', {'gt_id': first_instance.id}, **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    def get_open_data_object(self):
        ct = ContentType.objects.get_for_model(self.xform)
        _open_data, created = OpenData.objects.get_or_create(
            object_id=self.xform.id,
            defaults={
                'name': self.xform.id_string,
                'content_type': ct,
                'content_object': self.xform,
            }
        )

        return _open_data

    def test_update_open_data_with_valid_fields_and_data(self):
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        data = {'name': 'updated_name'}

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, 'Record was successfully updated.')

        _open_data = OpenData.objects.last()
        self.assertEqual(_open_data.name, 'updated_name')

    def test_update_open_data_with_invalid_fields_and_data(self):
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        data = {'invalid_key': 'invalid_value'}

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            'Valid fields are object_id, clazz and name.'
        )

        data = {
            'object_id': None,
            'clazz': None,
            'name': None
        }

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)

        data = {
            'object_id': 'invalid_object_id',
            'clazz': None,
            'name': None
        }

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            ("{'name': [u'This field is required.'], "
             "'object_id': [u'A valid integer is required.']}")
        )

    def test_delete_open_data_object(self):
        inital_count = OpenData.objects.count()
        _open_data = self.get_open_data_object()
        self.assertEqual(OpenData.objects.count(), inital_count + 1)
        request = self.factory.delete('/', **self.extra)
        response = self.view(request, uuid=_open_data.uuid)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(OpenData.objects.count(), inital_count)

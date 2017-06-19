from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse

from onadata.apps.logger.models import OsmData
from onadata.apps.logger.models.xform import XForm
from onadata.apps.logger.models.attachment import Attachment
from onadata.apps.logger.models.instance import Instance
from onadata.libs.renderers import renderers
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.libs.serializers.data_serializer import OSMSerializer
from onadata.libs.serializers.data_serializer import OSMSiteMapSerializer
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()


SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']


class OsmViewSet(AuthenticateHeaderMixin,
                 CacheControlMixin, ETagsMixin, BaseViewset,
                 ReadOnlyModelViewSet):

    """
This endpoint provides public access to OSM submitted data in OSM format.
No authentication is required. Where:

* `pk` - the form unique identifier
* `dataid` - submission data unique identifier
* `owner` - username of the owner(user/organization) of the data point

## GET JSON List of data end points

Lists the data endpoints accessible to requesting user, for anonymous access
a list of public data endpoints is returned.

<pre class="prettyprint">
<b>GET</b> /api/v1/osm
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/osm

## OSM

The `.osm` file format concatenates all the files for a form or individual
 submission. When the `.json` endpoint is accessed, the individual osm files
 are listed on the `_attachments` key.

### OSM endpoint for all osm files uploaded to a form concatenated.

<pre class="prettyprint">
<b>GET</b> /api/v1/osm/<code>{pk}</code>.osm
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/osm/28058.osm

### OSM endpoint with all osm files for a specific submission concatenated.

<pre class="prettyprint">
<b>GET</b> /api/v1/osm/<code>{pk}</code>/<code>{data_id}</code>.osm
</pre>

> Example
>
>       curl -X GET https://ona.io/api/v1/osm/28058/20.osm


"""
    renderer_classes = [
        renderers.OSMRenderer,
        JSONRenderer,
    ]

    serializer_class = OSMSerializer
    permission_classes = (AllowAny, )
    lookup_field = 'pk'
    lookup_fields = ('pk', 'dataid')
    extra_lookup_fields = None
    public_data_endpoint = 'public'

    queryset = XForm.objects.filter().select_related()

    def get_serializer_class(self):
        pk = self.kwargs.get('pk')
        if self.action == 'list' and pk is None:
            return OSMSiteMapSerializer

        return super(OsmViewSet, self).get_serializer_class()

    def filter_queryset(self, queryset):
        pk = self.kwargs.get('pk')
        if pk:
            queryset = queryset.filter(pk=pk)

        return super(OsmViewSet, self).filter_queryset(queryset)

    def get_object(self):
        obj = super(OsmViewSet, self).get_object()
        pk_lookup, dataid_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        dataid = self.kwargs.get(dataid_lookup)

        if pk is not None and dataid is not None:
            try:
                int(dataid)
            except ValueError:
                raise ParseError(_(u"Invalid dataid %(dataid)s"
                                   % {'dataid': dataid}))

            obj = get_object_or_404(Instance, pk=dataid, xform__pk=pk)

        return obj

    def retrieve(self, request, *args, **kwargs):
        fmt = kwargs.get('format', request.accepted_renderer.format)
        if fmt != 'osm':
            pk_lookup, dataid_lookup = self.lookup_fields
            pk = self.kwargs.get(pk_lookup)
            dataid = self.kwargs.get(dataid_lookup)
            kwargs = {'pk': pk, 'format': 'osm'}
            viewname = 'osm-list'
            if dataid:
                kwargs[dataid_lookup] = dataid
                viewname = 'osm-detail'

            return HttpResponsePermanentRedirect(
                reverse(viewname, kwargs=kwargs, request=request))

        instance = self.get_object()
        if isinstance(instance, XForm):
            osm_list = OsmData.objects.filter(instance__xform=instance)
        else:
            osm_list = OsmData.objects.filter(instance=instance)
        serializer = self.get_serializer(osm_list, many=True)

        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        fmt = kwargs.get('format', request.accepted_renderer.format)
        pk = kwargs.get('pk')
        if pk:
            if fmt != 'osm':
                return HttpResponsePermanentRedirect(
                    reverse('osm-list', kwargs={'pk': pk, 'format': 'osm'},
                            request=request))
            instance = self.filter_queryset(self.get_queryset())
            osm_list = OsmData.objects.filter(instance__xform__in=instance)
            page = self.paginate_queryset(osm_list)
            if page is not None:
                serializer = self.get_pagination_serializer(page)
            else:
                serializer = self.get_serializer(osm_list, many=True)

            return Response(serializer.data)

        if fmt == 'osm':
            return HttpResponsePermanentRedirect(
                reverse('osm-list', kwargs={'format': 'json'},
                        request=request))
        instances = Attachment.objects.filter(extension='osm').values(
            'instance__xform', 'instance__xform__user__username',
            'instance__xform__title', 'instance__xform__id_string')\
            .order_by('instance__xform__id')\
            .distinct('instance__xform__id')
        serializer = self.get_serializer(instances, many=True)

        return Response(serializer.data, content_type='application/json')

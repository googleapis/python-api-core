
from typing import Dict, Mapping, MutableMapping, MutableSequence, Optional, AsyncIterable, Awaitable, AsyncIterator, Sequence, Tuple, Type, Union

from .abstract_operations_client import AbstractOperationsClient
from google.api_core import gapic_v1  # type: ignore
from google.api_core import client_options as client_options_lib  # type: ignore
from google.api_core.operations_v1.transports.base import (
    DEFAULT_CLIENT_INFO,
    OperationsTransport,
)

from google.api_core import retry_async as retries
from google.auth import credentials as ga_credentials  # type: ignore
from google.longrunning import operations_pb2
import grpc
from google.api_core.operations_v1 import pagers
import functools

try:
    OptionalRetry = Union[retries.AsyncRetry, gapic_v1.method._MethodDefault, None]
except AttributeError:  # pragma: NO COVER
    OptionalRetry = Union[retries.AsyncRetry, object, None]  # type: ignore

class AbstractOperationsAsyncClient:
    """This service is used showcase the four main types of rpcs -
    unary, server side streaming, client side streaming, and
    bidirectional streaming. This service also exposes methods that
    explicitly implement server delay, and paginated calls. Set the
    'showcase-trailer' metadata key on any method to have the values
    echoed in the response trailers. Set the 'x-goog-request-params'
    metadata key on any method to have the values echoed in the
    response headers.
    """

    _client: AbstractOperationsClient

    # Copy defaults from the synchronous client for use here.
    # Note: DEFAULT_ENDPOINT is deprecated. Use _DEFAULT_ENDPOINT_TEMPLATE instead.
    DEFAULT_ENDPOINT = AbstractOperationsClient.DEFAULT_ENDPOINT
    DEFAULT_MTLS_ENDPOINT = AbstractOperationsClient.DEFAULT_MTLS_ENDPOINT

    common_billing_account_path = staticmethod(AbstractOperationsClient.common_billing_account_path)
    parse_common_billing_account_path = staticmethod(AbstractOperationsClient.parse_common_billing_account_path)
    common_folder_path = staticmethod(AbstractOperationsClient.common_folder_path)
    parse_common_folder_path = staticmethod(AbstractOperationsClient.parse_common_folder_path)
    common_organization_path = staticmethod(AbstractOperationsClient.common_organization_path)
    parse_common_organization_path = staticmethod(AbstractOperationsClient.parse_common_organization_path)
    common_project_path = staticmethod(AbstractOperationsClient.common_project_path)
    parse_common_project_path = staticmethod(AbstractOperationsClient.parse_common_project_path)
    common_location_path = staticmethod(AbstractOperationsClient.common_location_path)
    parse_common_location_path = staticmethod(AbstractOperationsClient.parse_common_location_path)

    @classmethod
    def from_service_account_info(cls, info: dict, *args, **kwargs):
        """Creates an instance of this client using the provided credentials
            info.

        Args:
            info (dict): The service account private key info.
            args: Additional arguments to pass to the constructor.
            kwargs: Additional arguments to pass to the constructor.

        Returns:
            AbstractOperationsAsyncClient: The constructed client.
        """
        return AbstractOperationsClient.from_service_account_info.__func__(AbstractOperationsAsyncClient, info, *args, **kwargs)  # type: ignore

    @classmethod
    def from_service_account_file(cls, filename: str, *args, **kwargs):
        """Creates an instance of this client using the provided credentials
            file.

        Args:
            filename (str): The path to the service account private key json
                file.
            args: Additional arguments to pass to the constructor.
            kwargs: Additional arguments to pass to the constructor.

        Returns:
            AbstractOperationsAsyncClient: The constructed client.
        """
        return AbstractOperationsClient.from_service_account_file.__func__(AbstractOperationsAsyncClient, filename, *args, **kwargs)  # type: ignore

    from_service_account_json = from_service_account_file

    @classmethod
    def get_mtls_endpoint_and_cert_source(cls, client_options: Optional[client_options_lib.ClientOptions] = None):
        """Return the API endpoint and client cert source for mutual TLS.

        The client cert source is determined in the following order:
        (1) if `GOOGLE_API_USE_CLIENT_CERTIFICATE` environment variable is not "true", the
        client cert source is None.
        (2) if `client_options.client_cert_source` is provided, use the provided one; if the
        default client cert source exists, use the default one; otherwise the client cert
        source is None.

        The API endpoint is determined in the following order:
        (1) if `client_options.api_endpoint` if provided, use the provided one.
        (2) if `GOOGLE_API_USE_CLIENT_CERTIFICATE` environment variable is "always", use the
        default mTLS endpoint; if the environment variable is "never", use the default API
        endpoint; otherwise if client cert source exists, use the default mTLS endpoint, otherwise
        use the default API endpoint.

        More details can be found at https://google.aip.dev/auth/4114.

        Args:
            client_options (google.api_core.client_options.client_options_lib.ClientOptions): Custom options for the
                client. Only the `api_endpoint` and `client_cert_source` properties may be used
                in this method.

        Returns:
            Tuple[str, Callable[[], Tuple[bytes, bytes]]]: returns the API endpoint and the
                client cert source to use.

        Raises:
            google.auth.exceptions.MutualTLSChannelError: If any errors happen.
        """
        return AbstractOperationsClient.get_mtls_endpoint_and_cert_source(client_options)  # type: ignore

    @property
    def transport(self) -> OperationsTransport:
        """Returns the transport used by the client instance.

        Returns:
            OperationsTransport: The transport used by the client instance.
        """
        return self._client.transport

    @property
    def api_endpoint(self):
        """Return the API endpoint used by the client instance.

        Returns:
            str: The API endpoint used by the client instance.
        """
        return self._client._api_endpoint

    @property
    def universe_domain(self) -> str:
        """Return the universe domain used by the client instance.

        Returns:
            str: The universe domain used
                by the client instance.
        """
        return self._client._universe_domain

    get_transport_class = functools.partial(type(AbstractOperationsClient).get_transport_class, type(AbstractOperationsClient))

    def __init__(self, *,
            credentials: Optional[ga_credentials.Credentials] = None,
            transport: Union[str, OperationsTransport] = "grpc_asyncio",
            client_options: Optional[client_options_lib.ClientOptions] = None,
            client_info: gapic_v1.client_info.ClientInfo = DEFAULT_CLIENT_INFO,
            ) -> None:
        """Instantiates the echo async client.

        Args:
            credentials (Optional[google.auth.credentials.Credentials]): The
                authorization credentials to attach to requests. These
                credentials identify the application to the service; if none
                are specified, the client will attempt to ascertain the
                credentials from the environment.
            transport (Union[str, ~.OperationsTransport]): The
                transport to use. If set to None, a transport is chosen
                automatically.
                NOTE: "rest" transport functionality is currently in a
                beta state (preview). We welcome your feedback via an
                issue in this library's source repository.
            client_options (Optional[Union[google.api_core.client_options.client_options_lib.ClientOptions, dict]]):
                Custom options for the client.

                1. The ``api_endpoint`` property can be used to override the
                default endpoint provided by the client when ``transport`` is
                not explicitly provided. Only if this property is not set and
                ``transport`` was not explicitly provided, the endpoint is
                determined by the GOOGLE_API_USE_MTLS_ENDPOINT environment
                variable, which have one of the following values:
                "always" (always use the default mTLS endpoint), "never" (always
                use the default regular endpoint) and "auto" (auto-switch to the
                default mTLS endpoint if client certificate is present; this is
                the default value).

                2. If the GOOGLE_API_USE_CLIENT_CERTIFICATE environment variable
                is "true", then the ``client_cert_source`` property can be used
                to provide a client certificate for mTLS transport. If
                not provided, the default SSL client certificate will be used if
                present. If GOOGLE_API_USE_CLIENT_CERTIFICATE is "false" or not
                set, no client certificate will be used.

                3. The ``universe_domain`` property can be used to override the
                default "googleapis.com" universe. Note that ``api_endpoint``
                property still takes precedence; and ``universe_domain`` is
                currently not supported for mTLS.

            client_info (google.api_core.gapic_v1.client_info.ClientInfo):
                The client info used to send a user-agent string along with
                API requests. If ``None``, then default info will be used.
                Generally, you only need to set this if you're developing
                your own client library.

        Raises:
            google.auth.exceptions.MutualTlsChannelError: If mutual TLS transport
                creation failed for any reason.
        """
        self._client = AbstractOperationsClient(
            credentials=credentials,
            transport=transport,
            client_options=client_options,
            client_info=client_info,

        )

    async def list_operations(
        self,
        name: str,
        filter_: Optional[str] = None,
        *,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
        retry: OptionalRetry = gapic_v1.method_async.DEFAULT,
        timeout: Optional[float] = None,
        compression: Optional[grpc.Compression] = gapic_v1.method.DEFAULT,
        metadata: Sequence[Tuple[str, str]] = (),
    ) -> pagers.ListOperationsPager:
        r"""Lists operations that match the specified filter in the request.
        If the server doesn't support this method, it returns
        ``UNIMPLEMENTED``.

        NOTE: the ``name`` binding allows API services to override the
        binding to use different resource name schemes, such as
        ``users/*/operations``. To override the binding, API services
        can add a binding such as ``"/v1/{name=users/*}/operations"`` to
        their service configuration. For backwards compatibility, the
        default name includes the operations collection id, however
        overriding users must ensure the name binding is the parent
        resource, without the operations collection id.

        Args:
            name (str):
                The name of the operation's parent
                resource.
            filter_ (str):
                The standard list filter.
                This corresponds to the ``filter`` field
                on the ``request`` instance; if ``request`` is provided, this
                should not be set.
            retry (google.api_core.retry.Retry): Designation of what errors, if any,
                should be retried.
            timeout (float): The timeout for this request.
            metadata (Sequence[Tuple[str, str]]): Strings which should be
                sent along with the request as metadata.

        Returns:
            google.api_core.operations_v1.pagers.ListOperationsPager:
                The response message for
                [Operations.ListOperations][google.api_core.operations_v1.Operations.ListOperations].

                Iterating over this object will yield results and
                resolve additional pages automatically.

        """
        # Create a protobuf request object.
        request = operations_pb2.ListOperationsRequest(name=name, filter=filter_)
        if page_size is not None:
            request.page_size = page_size
        if page_token is not None:
            request.page_token = page_token

        # Wrap the RPC method; this adds retry and timeout information,
        # and friendly error handling.
        rpc = self.transport._wrapped_methods[self.transport.list_operations]

        # Certain fields should be provided within the metadata header;
        # add these here.
        metadata = tuple(metadata or ()) + (
            gapic_v1.routing_header.to_grpc_metadata((("name", request.name),)),
        )

        # Send the request.
        response = await rpc(
            request,
            retry=retry,
            timeout=timeout,
            compression=compression,
            metadata=metadata,
        )

        # This method is paged; wrap the response in a pager, which provides
        # an `__iter__` convenience method.
        response = pagers.ListOperationsPager(
            method=rpc,
            request=request,
            response=response,
            metadata=metadata,
        )

        # Done; return the response.
        return response

    async def get_operation(
        self,
        name: str,
        *,
        retry: OptionalRetry = gapic_v1.method_async.DEFAULT,
        timeout: Optional[float] = None,
        compression: Optional[grpc.Compression] = gapic_v1.method.DEFAULT,
        metadata: Sequence[Tuple[str, str]] = (),
    ) -> operations_pb2.Operation:
        r"""Gets the latest state of a long-running operation.
        Clients can use this method to poll the operation result
        at intervals as recommended by the API service.

        Args:
            name (str):
                The name of the operation resource.
            retry (google.api_core.retry.Retry): Designation of what errors, if any,
                should be retried.
            timeout (float): The timeout for this request.
            metadata (Sequence[Tuple[str, str]]): Strings which should be
                sent along with the request as metadata.

        Returns:
            google.longrunning.operations_pb2.Operation:
                This resource represents a long-
                running operation that is the result of a
                network API call.

        """

        request = operations_pb2.GetOperationRequest(name=name)

        # Wrap the RPC method; this adds retry and timeout information,
        # and friendly error handling.
        rpc = self.transport._wrapped_methods[self.transport.get_operation]

        # Certain fields should be provided within the metadata header;
        # add these here.
        metadata = tuple(metadata or ()) + (
            gapic_v1.routing_header.to_grpc_metadata((("name", request.name),)),
        )

        # Send the request.
        response = await rpc(
            request,
            retry=retry,
            timeout=timeout,
            compression=compression,
            metadata=metadata,
        )

        # Done; return the response.
        return response

    async def delete_operation(
        self,
        name: str,
        *,
        retry: OptionalRetry = gapic_v1.method_async.DEFAULT,
        timeout: Optional[float] = None,
        compression: Optional[grpc.Compression] = gapic_v1.method.DEFAULT,
        metadata: Sequence[Tuple[str, str]] = (),
    ) -> None:
        r"""Deletes a long-running operation. This method indicates that the
        client is no longer interested in the operation result. It does
        not cancel the operation. If the server doesn't support this
        method, it returns ``google.rpc.Code.UNIMPLEMENTED``.

        Args:
            name (str):
                The name of the operation resource to
                be deleted.

                This corresponds to the ``name`` field
                on the ``request`` instance; if ``request`` is provided, this
                should not be set.
            retry (google.api_core.retry.Retry): Designation of what errors, if any,
                should be retried.
            timeout (float): The timeout for this request.
            metadata (Sequence[Tuple[str, str]]): Strings which should be
                sent along with the request as metadata.
        """
        # Create the request object.
        request = operations_pb2.DeleteOperationRequest(name=name)

        # Wrap the RPC method; this adds retry and timeout information,
        # and friendly error handling.
        rpc = self.transport._wrapped_methods[self.transport.delete_operation]

        # Certain fields should be provided within the metadata header;
        # add these here.
        metadata = tuple(metadata or ()) + (
            gapic_v1.routing_header.to_grpc_metadata((("name", request.name),)),
        )

        # Send the request.
        await rpc(
            request,
            retry=retry,
            timeout=timeout,
            compression=compression,
            metadata=metadata,
        )

    async def cancel_operation(
        self,
        name: Optional[str] = None,
        *,
        retry: OptionalRetry = gapic_v1.method_async.DEFAULT,
        timeout: Optional[float] = None,
        compression: Optional[grpc.Compression] = gapic_v1.method.DEFAULT,
        metadata: Sequence[Tuple[str, str]] = (),
    ) -> None:
        r"""Starts asynchronous cancellation on a long-running operation.
        The server makes a best effort to cancel the operation, but
        success is not guaranteed. If the server doesn't support this
        method, it returns ``google.rpc.Code.UNIMPLEMENTED``. Clients
        can use
        [Operations.GetOperation][google.api_core.operations_v1.Operations.GetOperation]
        or other methods to check whether the cancellation succeeded or
        whether the operation completed despite cancellation. On
        successful cancellation, the operation is not deleted; instead,
        it becomes an operation with an
        [Operation.error][google.api_core.operations_v1.Operation.error] value with
        a [google.rpc.Status.code][google.rpc.Status.code] of 1,
        corresponding to ``Code.CANCELLED``.

        Args:
            name (str):
                The name of the operation resource to
                be cancelled.

                This corresponds to the ``name`` field
                on the ``request`` instance; if ``request`` is provided, this
                should not be set.
            retry (google.api_core.retry.Retry): Designation of what errors, if any,
                should be retried.
            timeout (float): The timeout for this request.
            metadata (Sequence[Tuple[str, str]]): Strings which should be
                sent along with the request as metadata.
        """
        # Create the request object.
        request = operations_pb2.CancelOperationRequest(name=name)

        # Wrap the RPC method; this adds retry and timeout information,
        # and friendly error handling.
        rpc = self.transport._wrapped_methods[self.transport.cancel_operation]

        # Certain fields should be provided within the metadata header;
        # add these here.
        metadata = tuple(metadata or ()) + (
            gapic_v1.routing_header.to_grpc_metadata((("name", request.name),)),
        )

        # Send the request.
        await rpc(
            request,
            retry=retry,
            timeout=timeout,
            compression=compression,
            metadata=metadata,
        )

import io
import urllib.error

from rendering.providers.base import extract_http_error, openai_join_url
from rendering.providers.openai_images import _image_field_name


def test_openai_join_url_deduplicates_v1_when_base_and_endpoint_both_include_it():
    assert (
        openai_join_url("https://img.yman.cc/v1", "/v1/images/edits")
        == "https://img.yman.cc/v1/images/edits"
    )


def test_openai_join_url_adds_v1_for_image_endpoint_without_versioned_base():
    assert (
        openai_join_url("https://img.yman.cc", "/images/edits")
        == "https://img.yman.cc/v1/images/edits"
    )


def test_image2_proxy_uses_array_image_field_for_multiple_references():
    assert _image_field_name({"provider": "image2_proxy"}, 2) == "image[]"
    assert _image_field_name({"provider": "image2_proxy"}, 1) == "image"
    assert _image_field_name({"provider": "openai_compatible"}, 2) == "image"


def test_upstream_auth_error_does_not_become_app_auth_error():
    error = urllib.error.HTTPError(
        url="https://img.yman.cc/v1/images/edits",
        code=401,
        msg="Unauthorized",
        hdrs={},
        fp=io.BytesIO(b'{"error":{"message":"Invalid token"}}'),
    )
    provider_error = extract_http_error(error, "https://img.yman.cc/v1/images/edits")
    assert provider_error.status_code == 502
    assert "Invalid token" in provider_error.message

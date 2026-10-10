import json
from unittest import mock

import pytest


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    import os

    os.environ["SURF_CONTROLLER_CONFIG_DIR"] = str(tmp_path_factory.mktemp("cfg"))
    from surf_controller import api

    return api


def _response(status, body=None, text=None):
    r = mock.Mock(status_code=status)
    r.text = text if text is not None else json.dumps(body)
    if body is None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = body
    return r


def test_create_workspace_returns_new_id(api):
    with mock.patch.object(api.requests, "post", return_value=_response(201, {"id": "ws-42"})):
        assert api.Workspace().create_workspace({"name": "x"}) == (True, "ws-42")


def test_create_workspace_without_id_still_ok(api):
    with mock.patch.object(api.requests, "post", return_value=_response(201, text="")):
        assert api.Workspace().create_workspace({"name": "x"}) == (True, "OK")


def test_create_workspace_failure(api):
    with mock.patch.object(api.requests, "post", return_value=_response(400, {"detail": "bad"})):
        ok, msg = api.Workspace().create_workspace({"name": "x"})
    assert not ok and msg.startswith("Status 400")


def test_last_status_tracks_list_requests(api):
    ws = api.Workspace()
    assert ws.last_status is None
    with mock.patch.object(api.requests, "get", return_value=_response(403, {"detail": "no"})):
        assert ws.get_workspaces() == []
    assert ws.last_status == 403
    with mock.patch.object(api.requests, "get", return_value=_response(200, {"results": []})):
        assert ws.get_workspaces() == []
    assert ws.last_status == 200

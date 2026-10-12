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


def _ws(i):
    return {"id": f"ws-{i}", "name": f"vm-{i}", "active": True,
            "resource_meta": {"ip": f"10.0.0.{i}"}, "end_time": "", "owner_id": "o"}


def test_get_workspaces_follows_next_pages(api):
    base = "https://gw.example/v1/workspace/workspaces"
    pages = [
        _response(200, {"count": 3, "next": f"{base}/?limit=2&offset=2",
                        "results": [_ws(1), _ws(2)]}),
        _response(200, {"count": 3, "next": None, "results": [_ws(3)]}),
    ]
    with mock.patch.object(api.requests, "get", side_effect=pages) as get:
        got = api.Workspace().get_workspaces()
    assert [d.id for d in got] == ["ws-1", "ws-2", "ws-3"]
    assert get.call_count == 2
    assert get.call_args_list[1].args[0] == f"{base}/?limit=2&offset=2"
    assert get.call_args_list[1].kwargs["params"] is None


def test_get_workspaces_stops_on_failed_page(api):
    pages = [
        _response(200, {"count": 3, "next": "https://gw.example/p2", "results": [_ws(1)]}),
        _response(500, {"detail": "boom"}),
    ]
    ws = api.Workspace()
    with mock.patch.object(api.requests, "get", side_effect=pages):
        assert ws.get_workspaces() == []
    assert ws.last_status == 500


def test_get_workspaces_passes_name_filter(api):
    with mock.patch.object(api.requests, "get",
                           return_value=_response(200, {"count": 1, "next": None, "results": [_ws(7)]})) as get:
        got = api.Workspace().get_workspaces(name="vm-7")
    assert [d.name for d in got] == ["vm-7"]
    assert get.call_args.kwargs["params"] == {"name": "vm-7"}


def test_save_writes_all_pages(api, tmp_path):
    pages = [
        _response(200, {"count": 2, "next": "https://gw.example/p2", "results": [_ws(1)]}),
        _response(200, {"count": 2, "next": None, "results": [_ws(2)]}),
    ]
    ws = api.Workspace()
    ws.OUTPUT_FILE = tmp_path / "ids.csv"
    with mock.patch.object(api.requests, "get", side_effect=pages):
        ws.get_workspaces(save=True)
    assert ws.OUTPUT_FILE.read_text().count("\n") == 3

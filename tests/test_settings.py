from octoprint_pangolin_newt import clean_settings, valid_endpoint


def test_empty_secret_keeps_stored_one():
    data = clean_settings({"newt_id": " abc ", "newt_secret": "  "})
    assert data == {"newt_id": "abc"}


def test_secret_is_trimmed():
    assert clean_settings({"newt_secret": " s3cret\n"}) == {"newt_secret": "s3cret"}


def test_endpoint_trailing_slash_removed():
    data = clean_settings({"pangolin_endpoint": " https://pangolin.example.com/ "})
    assert data == {"pangolin_endpoint": "https://pangolin.example.com"}


def test_invalid_endpoint_is_not_saved():
    assert clean_settings({"pangolin_endpoint": "pangolin.example.com"}) == {}


def test_valid_endpoint():
    assert valid_endpoint("https://app.pangolin.net")
    assert valid_endpoint("http://10.0.0.5:3000")
    assert not valid_endpoint("ftp://x")
    assert not valid_endpoint("https://")

import pytest

from scripts.check_sensitive_identifiers import scan_text

ACCOUNT_FIELDS = (
    "unb",
    "tracknick",
    "cid",
    "toid",
    "sessionId",
    "userId",
    "send_user_id",
    "senderUserId",
    "peer_user_id",
    "mid",
    "msg_id",
)


@pytest.mark.parametrize("field", ACCOUNT_FIELDS)
@pytest.mark.parametrize(
    "template",
    (
        '"{field}": "{value}"',
        "'{field}': '{value}'",
        "{field}: {value}",
        '{field} = "{value}"',
        '"{field}":\n  "{value}"',
    ),
)
def test_rejects_sensitive_fields_in_common_serialization_formats(field, template):
    identifier = "221" + "4350705775"

    findings = scan_text(template.format(field=field, value=identifier))

    assert findings == [(1, "sensitive field contains a concrete identifier")]


def test_rejects_account_conversation_and_message_identifiers():
    account_id = "221" + "4350705775"
    conversation_id = "605" + "85751957"
    message_id = "407" + "71518" + "26249.PNM"
    text = "\n".join(
        [
            f'{{"unb":"{account_id}"}}',
            f'{{"cid":"{conversation_id}"}}',
            f'{{"msg_ids":["{message_id}"]}}',
            f'goofish message send {conversation_id} {account_id} --text hello',
            f'_make_cookie("unb", "{account_id}", ".taobao.com")',
            f'generate_device_id("{account_id}")',
        ]
    )

    findings = scan_text(text)

    assert {line for line, _ in findings} == {1, 2, 3, 4, 5, 6}


def test_rejects_cookie_header_assignments_and_tracknick_values():
    account_id = "221" + "4350705775"
    tracknick = "xy" + "575986224572"

    findings = scan_text(f"Cookie: unb={account_id}; tracknick={tracknick}")

    assert {description for _, description in findings} == {
        "sensitive field contains a concrete identifier",
        "concrete tracknick identifier",
    }


def test_allows_masked_values_fake_fixtures_and_public_item_ids():
    text = "\n".join(
        [
            '{"unb":"<masked-unb>","tracknick":"<masked-tracknick>"}',
            '{"cid":"test-cid","send_user_id":"test-user"}',
            "goofish item get 1045171414271",
        ]
    )

    assert scan_text(text) == []

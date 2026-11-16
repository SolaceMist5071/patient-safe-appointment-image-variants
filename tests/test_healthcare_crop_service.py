from src.healthcare_crop_service import AppointmentImageService, AppointmentRequest


class CropStub:
    def crop(self, image: str, x: int, y: int, width: int, height: int) -> dict:
        return {"data": {"url": f"{image}?crop={x},{y},{width},{height}"}}


def test_confirmed_consented_appointment_gets_all_requested_variants() -> None:
    service = AppointmentImageService(CropStub(), "clinic-images")
    request = AppointmentRequest("p-1", "a-1", "photos/intake.jpg", "confirmed", True)

    plan = service.prepare(request, ("1:1", "4:3", "16:9"))

    assert tuple(plan.image_variants) == ("1:1", "4:3", "16:9")
    assert plan.image_variants["4:3"].endswith("crop=0,0,1,1")
    assert plan.notification == "Appointment details are ready for the care team."


def test_unconfirmed_without_consent_sends_no_image_notification() -> None:
    service = AppointmentImageService(CropStub(), "clinic-images")
    request = AppointmentRequest("p-1", "a-1", "photos/intake.jpg", "requested", False)

    plan = service.prepare(request, ("1:1", "4:3"))

    assert plan.image_variants == {}
    assert "No image notification" in plan.notification

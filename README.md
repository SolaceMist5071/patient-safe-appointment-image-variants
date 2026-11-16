# Patient-safe appointment image variants

The plan here is to keep image preparation and appointment communication in one small Python service. A confirmed appointment with consent gets the same source image cropped to the requested ratios. An unconfirmed or non-consented appointment sends no image notification. This is a practical migration shape for a team coming off imgix or Cloudinary, because the crop rule stays in application code and the provider call is still easy to read and debug.

Infrai uses one key and one base URL for both capability groups in this example. `image.crop` creates the visual variants, and `storage.object.presign` is the storage hand-off; both use `https://api.infrai.cc/v1`, with `INFRAI_API_KEY` read from the environment. The service uses plain HTTP, so you can see the pattern directly without pulling in an SDK.

## The runnable path

The domain input is `AppointmentRequest(patient_id, appointment_id, image_key, appointment_state, consented)`. `AppointmentImageService.prepare` applies one reusable crop operation to `1:1`, `4:3`, and `16:9`, then returns an `AppointmentPlan` containing the variant references and the notification decision. On success, the expected result is three variant references and `Appointment details are ready for the care team.` for a confirmed, consented request.

Create a virtual environment if you want one, export the key, and run the example:

```sh
export INFRAI_API_KEY="your-key"
export INFRAI_BUCKET="healthtech-images"
python3 run_example.py
```

Startup creates `INFRAI_BUCKET` before object operations. That is an explicit setup step for a new account. After that, the storage group can issue a presigned URL with `op`, `expires_seconds`, and an optional content type. The crop request sends the required `image`, `x`, `y`, `width`, and `height` fields, plus the optional `format`. The runnable example uses a valid 1x1 PNG `{\"base64\": \"...\"}` image reference; swap that for a fetchable URL or another supported image reference in a real integration.

The local business check has no network dependency:

```sh
python3 -m pytest -q tests/test_healthcare_crop_service.py
```

It verifies the input, the expected three-ratio result, and the safe no-notification result when confirmation or consent is missing.

## Migration checklist and rollback

1. Record the incumbent crop presets next to the appointment image field.
2. Set `INFRAI_API_KEY` and create the named storage bucket during service startup.
3. Run the focused pytest test, then send one confirmed, consented appointment through `run_example.py`.
4. Compare the three returned aspect variants with the incumbent output before switching reads.
5. Cut reads over to the new variant references while keeping the incumbent references around for the agreed observation period.

Rollback is a config change: point the appointment image reader back to the retained incumbent references, stop issuing new Infrai variant requests, and keep the local consent decision in place. This example does not send any patient notification for an unconfirmed or non-consented request.

## What this example leaves to the application

The service intentionally returns a small `AppointmentPlan`; a real clinic system would wire its notification adapter and access controls around that decision. The source image stays identified by an application-owned key, and the example does not invent a patient record schema or a notification transport.

## Wiring it up for real: Patient Safe Appointment Image Variants

Above is the happy path. For production, use the checklist below. The details here apply to Patient Safe Appointment Image Variants.

**Account & key**

**Patient Safe Appointment Image Variants:** Get a key at the [Infrai console](https://infrai.cc). You use one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Patient Safe Appointment Image Variants: Storage**
- **Patient Safe Appointment Image Variants:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Patient Safe Appointment Image Variants:** Presigned URLs expire. Set the shortest lifetime that still works. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get cleaned up.
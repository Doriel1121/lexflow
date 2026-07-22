import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "2m", target: 10 },
    { duration: "5m", target: 50 },
    { duration: "5m", target: 100 },
    { duration: "2m", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    "http_req_duration{kind:non_ai}": ["p(95)<500"],
    "http_req_duration{kind:ai}": ["p(95)<5000"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const EMAIL = __ENV.TEST_EMAIL;
const PASSWORD = __ENV.TEST_PASSWORD;
const SEARCH_QUERY = __ENV.SEARCH_QUERY || "הסכם";

export function setup() {
  if (!EMAIL || !PASSWORD) {
    throw new Error("Set TEST_EMAIL and TEST_PASSWORD environment variables.");
  }

  const response = http.post(`${BASE_URL}/token`, {
    username: EMAIL,
    password: PASSWORD,
  });

  check(response, {
    "login ok": (res) => res.status === 200 && !!res.json("access_token"),
  });

  return { token: response.json("access_token") };
}

export default function (data) {
  const params = {
    headers: { Authorization: `Bearer ${data.token}` },
    tags: { kind: "non_ai" },
  };

  check(http.get(`${BASE_URL}/v1/documents/?skip=0&limit=50`, params), {
    "documents list ok": (res) => res.status === 200,
  });

  check(
    http.get(
      `${BASE_URL}/v1/documents/?skip=0&limit=50&search=${encodeURIComponent(SEARCH_QUERY)}`,
      params,
    ),
    { "document search ok": (res) => res.status === 200 },
  );

  check(http.get(`${BASE_URL}/v1/notifications?skip=0&limit=100`, params), {
    "notifications ok": (res) => res.status === 200,
  });

  if (Math.random() < 0.1) {
    const aiParams = {
      headers: { Authorization: `Bearer ${data.token}` },
      tags: { kind: "ai" },
    };
    check(
      http.get(
        `${BASE_URL}/v1/documents/semantic-search?query=${encodeURIComponent(SEARCH_QUERY)}&limit=10`,
        aiParams,
      ),
      { "semantic search handled": (res) => [200, 503, 429].includes(res.status) },
    );
  }

  sleep(Math.random() * 3);
}
import assert from "node:assert/strict";
import test from "node:test";
import { AxiosError } from "axios";
import { api, generateCad } from "./api.ts";
import type { DoorFormData } from "./types.ts";

const formData = {} as DoorFormData;
type CadRequestError = AxiosError & { userMessage?: string };

test("CAD timeout reports processing or download delay, not a network diagnosis", async (t) => {
  const adapter = api.defaults.adapter;
  t.after(() => { api.defaults.adapter = adapter; });
  api.defaults.adapter = async (config) => {
    assert.equal(config.timeout, 60000);
    throw new AxiosError("timeout of 60000ms exceeded", "ECONNABORTED", config);
  };
  await assert.rejects(generateCad(formData), (error: CadRequestError) => {
    assert.equal(error.code, "ECONNABORTED");
    assert.equal(error.userMessage, "DXF 文件生成或下载超时，请稍后重试");
    return true;
  });
});

test("CAD network failures retain the existing network message", async (t) => {
  const adapter = api.defaults.adapter;
  t.after(() => { api.defaults.adapter = adapter; });
  api.defaults.adapter = async (config) => {
    throw new AxiosError("Network Error", "ERR_NETWORK", config);
  };
  await assert.rejects(generateCad(formData), (error: CadRequestError) => {
    assert.equal(error.code, "ERR_NETWORK");
    assert.equal(error.userMessage, "网络连接失败，请检查服务器状态");
    return true;
  });
});

test("CAD server Blob error details remain visible", async (t) => {
  const adapter = api.defaults.adapter;
  t.after(() => { api.defaults.adapter = adapter; });
  api.defaults.adapter = async (config) => {
    throw new AxiosError("Request failed", "ERR_BAD_RESPONSE", config, undefined, {
      config,
      data: new Blob([JSON.stringify({ detail: "DXF 生成失败：图框实体无法转换" })]),
      status: 500,
      statusText: "Internal Server Error",
      headers: {},
    });
  };
  await assert.rejects(generateCad(formData), (error: CadRequestError) => {
    assert.equal(error.response?.status, 500);
    assert.equal(error.userMessage, "DXF 生成失败：图框实体无法转换");
    return true;
  });
});

test("successful DXF requests return the original Blob and keep the timeout", async (t) => {
  const adapter = api.defaults.adapter;
  t.after(() => { api.defaults.adapter = adapter; });
  const content = "  0\nSECTION\n  2\nENTITIES\n  0\nENDSEC\n  0\nEOF\n";
  const blob = new Blob([content], { type: "application/octet-stream" });
  api.defaults.adapter = async (config) => {
    assert.equal(config.method, "post");
    assert.equal(config.url, "/generate_cad");
    assert.equal(config.responseType, "blob");
    assert.equal(config.timeout, 60000);
    return { config, data: blob, status: 200, statusText: "OK", headers: {} };
  };
  const result = await generateCad(formData);
  assert.equal(result, blob);
  assert.equal(await result.text(), content);
});

test("non-CAD timeout handling is unchanged", async (t) => {
  const adapter = api.defaults.adapter;
  t.after(() => { api.defaults.adapter = adapter; });
  api.defaults.adapter = async (config) => {
    throw new AxiosError("timeout", "ECONNABORTED", config);
  };
  await assert.rejects(api.get("/tasks"), (error: CadRequestError) => {
    assert.equal(error.userMessage, "请求超时，请检查网络后重试");
    return true;
  });
});

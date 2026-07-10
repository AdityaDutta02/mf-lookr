const GATEWAY = process.env.TERMINAL_AI_GATEWAY_URL!;

interface CreateTaskParams {
  name: string;
  schedule: string;
  callbackPath: string;
  payload?: Record<string, unknown>;
  timezone?: string;
}

export async function createTask(
  params: CreateTaskParams,
  embedToken: string,
): Promise<{ id: string; nextRunAt: string }> {
  const res = await fetch(`${GATEWAY}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${embedToken}` },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(`Task creation failed (${res.status}): ${(err as Record<string, string>).error ?? res.statusText}`);
  }
  return res.json();
}

export async function listTasks(
  embedToken: string,
): Promise<Array<{ id: string; name: string; schedule: string; enabled: boolean; nextRunAt: string | null }>> {
  const res = await fetch(`${GATEWAY}/tasks`, { headers: { Authorization: `Bearer ${embedToken}` } });
  if (!res.ok) throw new Error(`Task list failed: ${res.status}`);
  return res.json();
}

export async function deleteTask(taskId: string, embedToken: string): Promise<{ deleted: boolean }> {
  const res = await fetch(`${GATEWAY}/tasks/${taskId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${embedToken}` } });
  if (!res.ok) throw new Error(`Task delete failed: ${res.status}`);
  return res.json();
}

export interface CreateDelayedTaskParams {
  name: string;
  callbackPath: string;
  delayMinutes: number; // 1-1440
  payload?: Record<string, unknown>;
}

export async function createDelayedTask(
  params: CreateDelayedTaskParams,
  embedToken: string,
): Promise<{ id: string; nextRunAt: string; oneShot: true }> {
  const res = await fetch(`${GATEWAY}/tasks/delayed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${embedToken}` },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(`Delayed task creation failed (${res.status}): ${(err as Record<string, string>).error ?? res.statusText}`);
  }
  return res.json();
}

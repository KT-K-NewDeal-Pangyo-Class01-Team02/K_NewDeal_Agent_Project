import { useCallback, useState } from 'react';

function readSet(storageKey: string): Set<string> {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? new Set(parsed.filter((v) => typeof v === 'string')) : new Set();
  } catch {
    // 시크릿 모드나 저장소 차단 환경에서도 화면은 정상 동작해야 한다.
    return new Set();
  }
}

/**
 * 완료 처리한 항목의 id를 localStorage에 저장해 새로고침 후에도 유지한다.
 */
export function usePersistentSet(storageKey: string) {
  const [ids, setIds] = useState<Set<string>>(() => readSet(storageKey));

  const persist = useCallback(
    (next: Set<string>) => {
      setIds(next);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify([...next]));
      } catch {
        // 저장에 실패해도 현재 세션의 화면 상태는 그대로 유지한다.
      }
    },
    [storageKey],
  );

  const add = useCallback(
    (id: string) => persist(new Set(ids).add(id)),
    [ids, persist],
  );

  const remove = useCallback(
    (id: string) => {
      const next = new Set(ids);
      next.delete(id);
      persist(next);
    },
    [ids, persist],
  );

  return { ids, add, remove };
}

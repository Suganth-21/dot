import { useMutation, useQueryClient } from "@tanstack/react-query";

// Wraps a service mutation fn; invalidates all queries once on completion so
// lists/dashboards reflect the change. (Live maps use useLive, not queries.)
export function useAppMutation(fn, options = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    ...options,
    onSettled: (...args) => {
      qc.invalidateQueries();
      options.onSettled?.(...args);
    },
  });
}

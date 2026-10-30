"use client";

import {
  KeyboardEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  ClassifierCapability,
  ClassifierModelId,
} from "@/types/classification";

interface ClassifierModelSelectProps {
  classifiers: ClassifierCapability[];
  value: ClassifierModelId;
  loading: boolean;
  disabled?: boolean;
  onChange: (modelId: ClassifierModelId) => void;
}

interface ModelOption {
  id: ClassifierModelId;
  name: string;
  description: string;
  available: boolean;
  mark: string;
  status: string;
}

export function getNextEnabledIndex(
  availability: boolean[],
  currentIndex: number,
  direction: 1 | -1,
): number {
  if (availability.length === 0) return -1;
  for (let offset = 1; offset <= availability.length; offset += 1) {
    const index = (currentIndex + direction * offset + availability.length) % availability.length;
    if (availability[index]) return index;
  }
  return -1;
}

function getModelMark(modelId: ClassifierModelId): string {
  if (modelId === "alexnet") return "AN";
  if (modelId === "resnet50") return "R50";
  if (modelId === "vit") return "ViT";
  return "OFF";
}

function getStatusClass(option: ModelOption): string {
  if (option.id === "none") return "manual";
  return option.available ? "available" : "planned";
}

export function ClassifierModelSelect({
  classifiers,
  value,
  loading,
  disabled = false,
  onChange,
}: ClassifierModelSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const labelId = useId();
  const listboxId = useId();

  const options = useMemo<ModelOption[]>(
    () => [
      {
        id: "none",
        name: "Không dùng model",
        description: "Tự chọn danh mục tìm kiếm",
        available: true,
        mark: getModelMark("none"),
        status: "Thủ công",
      },
      ...classifiers.map((classifier) => ({
        id: classifier.id,
        name: classifier.display_name,
        description: classifier.available
          ? `${classifier.input_size?.join("×") ?? "Kích thước linh hoạt"} · Phiên bản ${classifier.version}`
          : "Đang chờ checkpoint và cấu hình",
        available: classifier.available,
        mark: getModelMark(classifier.id),
        status: classifier.available ? "Khả dụng" : "Sắp tích hợp",
      })),
    ],
    [classifiers],
  );

  const selectedOption = options.find((option) => option.id === value) ?? options[0];
  const availability = options.map((option) => option.available);

  useEffect(() => {
    if (!open) return;
    const closeOnOutsidePointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    return () => document.removeEventListener("pointerdown", closeOnOutsidePointer);
  }, [open]);

  function focusOption(index: number) {
    window.requestAnimationFrame(() => optionRefs.current[index]?.focus());
  }

  function openMenu(preferredIndex?: number) {
    if (disabled) return;
    setOpen(true);
    const selectedIndex = options.findIndex((option) => option.id === value);
    focusOption(preferredIndex ?? Math.max(0, selectedIndex));
  }

  function closeMenu({ restoreFocus = true } = {}) {
    setOpen(false);
    if (restoreFocus) window.requestAnimationFrame(() => triggerRef.current?.focus());
  }

  function selectOption(option: ModelOption) {
    if (!option.available) return;
    onChange(option.id);
    closeMenu();
  }

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const selectedIndex = options.findIndex((option) => option.id === value);
      const nextIndex = event.key === "ArrowDown"
        ? getNextEnabledIndex(availability, selectedIndex - 1, 1)
        : getNextEnabledIndex(availability, selectedIndex + 1, -1);
      openMenu(nextIndex);
    }
  }

  function onOptionKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeMenu();
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const target = event.key === "Home"
        ? availability.findIndex(Boolean)
        : availability.findLastIndex(Boolean);
      focusOption(target);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const nextIndex = getNextEnabledIndex(
        availability,
        index,
        event.key === "ArrowDown" ? 1 : -1,
      );
      focusOption(nextIndex);
    }
  }

  return (
    <div className={`model-picker${open ? " open" : ""}`} ref={rootRef}>
      <span className="model-picker-label" id={labelId}>Model phân loại</span>
      <button
        aria-controls={listboxId}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-labelledby={`${labelId} classifier-model-value`}
        className="model-picker-trigger"
        disabled={disabled}
        id="classifier-model"
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={onTriggerKeyDown}
        ref={triggerRef}
        type="button"
      >
        <span className={`model-mark model-mark-${selectedOption.id}`} aria-hidden="true">
          {selectedOption.mark}
        </span>
        <span className="model-picker-value" id="classifier-model-value">
          <strong>{selectedOption.name}</strong>
          <small>{selectedOption.description}</small>
        </span>
        <span className={`model-status ${getStatusClass(selectedOption)}`}>
          {selectedOption.status}
        </span>
        <span className="model-picker-chevron" aria-hidden="true">⌄</span>
      </button>

      {open ? (
        <div aria-labelledby={labelId} className="model-picker-menu" id={listboxId} role="listbox">
          <div className="model-picker-menu-heading">
            <strong>Chọn cách phân loại</strong>
            <span>Mỗi lần chỉ sử dụng một model</span>
          </div>
          <div className="model-picker-options">
            {options.map((option, index) => {
              const selected = option.id === value;
              return (
                <button
                  aria-disabled={!option.available}
                  aria-selected={selected}
                  className={`model-picker-option${selected ? " selected" : ""}`}
                  disabled={!option.available}
                  key={option.id}
                  onClick={() => selectOption(option)}
                  onKeyDown={(event) => onOptionKeyDown(event, index)}
                  ref={(element) => { optionRefs.current[index] = element; }}
                  role="option"
                  tabIndex={selected || (value === "none" && index === 0) ? 0 : -1}
                  type="button"
                >
                  <span className={`model-mark model-mark-${option.id}`} aria-hidden="true">{option.mark}</span>
                  <span className="model-option-copy">
                    <strong>{option.name}</strong>
                    <small>{option.description}</small>
                  </span>
                  <span className={`model-status ${getStatusClass(option)}`}>{option.status}</span>
                  <span className="model-option-check" aria-hidden="true">{selected ? "✓" : ""}</span>
                </button>
              );
            })}
            {loading ? <div className="model-picker-loading" role="status">Đang cập nhật model khả dụng…</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

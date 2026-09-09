"use client";

import { useId } from "react";
import {
  broadJurisdictions,
  jurisdictionLabels,
  usStateJurisdictions,
} from "@/lib/jurisdictions";

interface JurisdictionSelectProps {
  includeGlobal?: boolean;
  label: string;
  onChange: (value: string[]) => void;
  value: string[];
}

export function JurisdictionSelect({
  includeGlobal = false,
  label,
  onChange,
  value,
}: JurisdictionSelectProps) {
  const selectId = useId();
  const broadOptions = broadJurisdictions.filter(
    (option) => includeGlobal || option.value !== "GLOBAL",
  );

  function addLocation(location: string) {
    if (!location) return;
    if (location === "GLOBAL") {
      onChange([location]);
      return;
    }
    onChange([...value.filter((item) => item !== "GLOBAL"), location]);
  }

  return (
    <div className="field jurisdiction-field">
      <label htmlFor={selectId}>{label}</label>
      <select
        id={selectId}
        value=""
        onChange={(event) => addLocation(event.target.value)}
      >
        <option value="" disabled>
          {value.length ? "Add another location" : "Select a location"}
        </option>
        <optgroup label="Countries and regions">
          {broadOptions.map((option) => (
            <option
              value={option.value}
              disabled={value.includes(option.value)}
              key={option.value}
            >
              {option.label}
            </option>
          ))}
        </optgroup>
        <optgroup label="United States — states">
          {usStateJurisdictions.map((option) => (
            <option
              value={option.value}
              disabled={value.includes(option.value)}
              key={option.value}
            >
              {option.label}
            </option>
          ))}
        </optgroup>
      </select>
      {value.length ? (
        <div
          className="jurisdiction-field__selected"
          aria-label="Selected locations"
        >
          {value.map((location) => (
            <span key={location}>
              {jurisdictionLabels.get(location) ?? location}
              <button
                type="button"
                onClick={() =>
                  onChange(value.filter((item) => item !== location))
                }
                aria-label={`Remove ${jurisdictionLabels.get(location) ?? location}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

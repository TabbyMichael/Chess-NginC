/**
 * Achievement gallery (ACH-005): the whole catalog with real progress.
 *
 * Everything on this page comes from `GET /me/achievements` — the server owns
 * the catalog and the counting, so the frontend only groups, labels and shows
 * how close each locked tile is.
 */
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { Badge } from '../components/ui/Badge';
import { DEFAULT_GROUP_ICON, GROUP_ICONS } from '../lib/achievement-icons';
import {
  TIER_LABELS,
  filterByGroup,
  formatCounter,
  formatUnlockedAt,
  groupLabel,
  groupsOf,
  progressPercent,
  sortForGallery,
} from '../lib/achievements';
import { ApiError, api } from '../lib/api-client';
import type { AchievementListResponse, AchievementProgressResponse } from '../lib/api-types';

function GroupGlyph({ group }: { group: string }) {
  // A map lookup keeps the icon's identity stable across renders.
  const Icon = GROUP_ICONS[group] ?? DEFAULT_GROUP_ICON;
  return <Icon size={18} aria-hidden="true" />;
}

function tileDetail(item: AchievementProgressResponse): string {
  const tier = TIER_LABELS[item.tier] ?? item.tier;
  if (item.unlocked) {
    const when = formatUnlockedAt(item.unlocked_at);
    return when ? `${tier} · ${when}` : tier;
  }
  return `${tier} · ${formatCounter(item.value, item.threshold)}`;
}

export default function AchievementsPage() {
  const [data, setData] = useState<AchievementListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [group, setGroup] = useState('all');

  useEffect(() => {
    let cancelled = false;
    api
      .listAchievements()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : 'Failed to load achievements');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const items = useMemo(() => (data ? sortForGallery(data.items) : []), [data]);
  const groups = useMemo(() => groupsOf(items), [items]);
  const shown = useMemo(() => filterByGroup(items, group), [items, group]);
  const sections = useMemo(
    () =>
      groups
        .map((name) => ({ name, entries: shown.filter((item) => item.group === name) }))
        .filter((section) => section.entries.length > 0),
    [groups, shown],
  );

  const overall = data && data.total > 0 ? progressPercent(data.unlocked / data.total) : 0;

  return (
    <main id="main-content" className="achievements-page">
      <div className="achievements-header">
        <div>
          <h1>Achievements</h1>
          <p className="u-muted">
            {data
              ? `${data.unlocked} of ${data.total} unlocked — every one earned by playing.`
              : 'Earned by playing: moves, captures, results, habits and reviews.'}
          </p>
        </div>
        <Link to="/" className="btn btn-ghost btn-small">
          <ArrowLeft size={14} aria-hidden="true" />
          Back to dashboard
        </Link>
      </div>

      {loading && (
        <p role="status" className="loading-state">
          Loading achievements…
        </p>
      )}
      {error && (
        <p role="alert" className="alert-error">
          {error}
        </p>
      )}

      {data && !loading && (
        <>
          <div className="achievement-summary">
            <span
              className="achievement-summary-bar"
              role="img"
              aria-label={`${overall}% of the catalog unlocked`}
            >
              <span className="achievement-summary-fill" style={{ width: `${overall}%` }} />
            </span>
            <span className="achievement-summary-text">{`${overall}% complete`}</span>
          </div>

          <div className="achievement-filters" role="group" aria-label="Filter by category">
            {['all', ...groups].map((name) => (
              <button
                key={name}
                type="button"
                className={`toggle-chip${group === name ? ' on' : ''}`}
                aria-pressed={group === name}
                onClick={() => setGroup(name)}
              >
                {name === 'all' ? 'All' : groupLabel(name)}
              </button>
            ))}
          </div>

          {sections.map((section) => (
            <section
              key={section.name}
              className="achievement-section"
              aria-label={groupLabel(section.name)}
            >
              <h2 className="achievement-section-title">
                <GroupGlyph group={section.name} />
                {groupLabel(section.name)}
              </h2>
              <div className="achievement-grid">
                {section.entries.map((item) => (
                  <Badge
                    key={item.key}
                    name={item.title}
                    desc={item.description}
                    icon={<GroupGlyph group={item.group} />}
                    unlocked={item.unlocked}
                    className={`tier-${item.tier}`}
                    progress={item.unlocked ? 1 : item.progress}
                    detail={tileDetail(item)}
                  />
                ))}
              </div>
            </section>
          ))}

          <p className="hint achievement-footnote">
            Achievements are counted from your real games: moves and captures from the stored move
            history, results from the points ledger, streaks from the days you played, and review
            grades from the engine analysis. <Link to="/lobby">Queue an online match</Link> or start
            a game from the dashboard to keep climbing.
          </p>
        </>
      )}
    </main>
  );
}

// 纸偶：角色拆成纸片部件，用关节连起来，由代码驱动（剪纸动画的做法，如 1958 年的《猪八戒吃西瓜》）。
//
// 每个角色可以有几个视角（view），每个视角一套部件：side = 侧面（走、跑、干活），q = 45° 半正面（站着说话、做表情）。
// 部件和关节写在 video/assets/rig/<角色视角>/rig.json（坐标都是部件图片里的像素）：
//   parts: { 名字: { pivot: [x,y] 这块纸片绕着转的关节, tip: [x,y] 骨头的另一端, size 单独缩放, ...附着点 } }
//   torso 上的附着点：neck、shoulderF/shoulderB、hipF/hipB（F = 靠近观众的一侧，B = 远的一侧）
//   head 上：knot（飘带）、mouth [x,y,宽]、eyes [[x,y,rx,ry],...]、skin（取肤色的点）
//   手臂：upper → forearm → 手（hands 把手形 open/fist/point/up/wave 映射到部件），手腕能单独转
//   scale：部件像素 → 画面像素；ankleH：脚踝到鞋底的高度（部件像素）
// 角度约定（面朝右的局部坐标，画布 y 向下）：0 = 竖直向下，正 = 往前转，方向 d(θ) = (sin θ, cos θ)。
// 面朝左时整个角色水平镜像；换视角时像纸片一样翻个面（0.22 秒）。
//
// 动作 = 基础层（按 keys 里的位移自动走/跑：步幅跟着速度走，着地的脚不打滑）
//       + 动作层（actions: [开始, 结束, 名字, 参数]，两头淡入淡出，和基础层混合）
//       + 跳跃（jumps: [起跳, 落地, 高度]，自带起跳前下蹲和落地缓冲）
// 角色手里的道具（扛木杆、捧金子）由场景通过 a.hook 提供：双手要握的点、道具的画法、画在哪一层。

const P = (() => {
  const TAU = Math.PI * 2;
  const smooth = x => x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x);
  const lerp = (a, b, u) => a + (b - a) * u;
  const dir = th => [Math.sin(th), Math.cos(th)];
  const ang = (vx, vy) => Math.atan2(vx, vy);
  const add = (a, b, k = 1) => [a[0] + b[0] * k, a[1] + b[1] * k];
  function rand(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  // 把部件放成「pivot 在 at、骨头朝 θ」：返回画布旋转角，以及把部件上的点换算到局部坐标的函数
  function place(rig, name, at, th) {
    const p = rig.parts[name], s = rig.scale * (p.size || 1);
    const rest = ang(p.tip[0] - p.pivot[0], p.tip[1] - p.pivot[1]);
    const phi = rest - th, c = Math.cos(phi), sn = Math.sin(phi);
    const map = q => { const x = (q[0] - p.pivot[0]) * s, y = (q[1] - p.pivot[1]) * s; return [at[0] + x * c - y * sn, at[1] + x * sn + y * c]; };
    return { name, at, phi, map, s };
  }
  const boneLen = (rig, n) => Math.hypot(rig.parts[n].tip[0] - rig.parts[n].pivot[0], rig.parts[n].tip[1] - rig.parts[n].pivot[1]) * rig.scale * (rig.parts[n].size || 1);

  // 两节骨骼反向运动学：从 A 够到 T；bend = +1 关节朝前弯（膝盖），-1 朝后（手肘）
  function ik(A, T, L1, L2, bend) {
    const vx = T[0] - A[0], vy = T[1] - A[1], d0 = Math.hypot(vx, vy) || 1e-3;
    const d = Math.max(Math.abs(L1 - L2) + 1e-3, Math.min(L1 + L2 - 1e-3, d0));
    const a = Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))));
    const th1 = ang(vx, vy) + bend * a, K = add(A, dir(th1), L1);
    const R = [A[0] + vx / d0 * d, A[1] + vy / d0 * d];
    return [th1, ang(R[0] - K[0], R[1] - K[1])];
  }

  // ---------- 动作层 ----------
  // 返回要覆盖的姿势字段：lean 身体前倾, head 点头, look 朝向（1 朝前 / -1 回头，连续值 = 纸片翻面）,
  // drop 下蹲(0–1), lift 离地, armF/armB [肩角, 肘弯], handF/handB 手形, wristF/wristB 手腕转角,
  // grip 双手握道具的权重, reach 伸手够的世界坐标, eyes 'open'|'happy'|'wide', smile, laugh, happy
  const flip = (s, s0, dur = 0.16) => Math.cos(Math.PI * smooth((s - s0) / dur));
  const ACTIONS = {
    talk: (u, d, a, t, p, view) => { const b = Math.sin(t * 7 + a.phase), b2 = Math.sin(t * 3.1 + 1);
      return view === 'q'   // 半正面：近侧的手在胸前摊开比划，手腕跟着节拍翻
        ? { armF: [0.55 + 0.25 * b, 1.35 + 0.3 * b2], handF: 'open', wristF: -0.35 + 0.35 * b, head: 0.05 * b, lean: 0.02 }
        : { armF: [0.75 + 0.3 * b, 1.1 + 0.35 * b2], handF: 'open', wristF: -0.2 + 0.3 * b, head: 0.05 * b, lean: 0.03 }; },
    fist: (u, d) => { const s = u * d, up = smooth(s / 0.22), pump = Math.sin(Math.min(1, s / 0.5) * Math.PI);
      // 胸前「耶！」：手肘往下往后一拉，拳头停在胸口高度（不挡脸）
      return { armF: [lerp(0.2, -0.45, up) - 0.2 * pump, lerp(0.8, 2.5, up)], armB: [0.2, 1.8], handF: 'fist', handB: 'fist', drop: 0.2 * pump, lean: 0.06 * pump - 0.03, eyes: 'wide', smile: 1 }; },
    reach: (u, d, a, t, p) => { const k = Math.min(p.stop ?? 1, smooth(u * d / 0.55));
      return { reach: p.target, reachW: k, lean: 0.22 * k, drop: 0.2 * k, handF: 'open', wristF: 0.25 }; },
    look: (u, d) => { const s = u * d;   // 回头看一眼身后、转回来，再看一眼、转回来
      const l = s < 0.55 ? flip(s, 0.08) : s < 1.0 ? -flip(s, 0.55) : s < 1.45 ? flip(s, 1.0) : -flip(s, 1.45);
      return { look: l, head: -0.06, eyes: 'wide', lean: -0.04 }; },
    crouch: u => ({ drop: 0.6 * Math.sin(u * Math.PI / 2), lean: 0.35 * Math.sin(u * Math.PI / 2), armF: [0.5, 0.6], armB: [0.4, 0.6] }),
    lift: (u, d, a, t) => { const rise = smooth((u - 0.35) / 0.65);   // 先蹲下抓住，再使劲站起来（抖一抖）
      return { grip: 1, drop: lerp(0.6, 0.34, rise), lean: lerp(0.3, -0.24, rise) + 0.03 * Math.sin(t * 43) * (1 - rise), handF: u > 0.4 ? 'up' : 'fist', handB: u > 0.4 ? 'up' : 'fist', strain: 1 }; },
    carry: (u, d, a, t) => ({ grip: 1, handF: 'up', handB: 'up', lean: -0.24, drop: 0.34, head: 0.14, smile: 0, strain: 0.9 }),   // 抱着重木杆：身子稍往后仰来平衡，屈膝，低头使劲   // 扛着重木杆：弓背、屈膝，一只手扣住、一只手托住
    drop: u => ({ grip: 1 - smooth((u - 0.85) / 0.12), drop: 0.34 + 0.3 * smooth((u - 0.3) / 0.4), lean: lerp(-0.24, 0.55, smooth((u - 0.2) / 0.4)), head: 0.25 * smooth((u - 0.3) / 0.4),
                  armF: [0.3, 0.5], armB: [0.2, 0.5], handF: 'up', handB: 'up', strain: 1 - smooth((u - 0.8) / 0.2) }),   // 卸到腰前，弯腰低头放下
    lookup: (u, d, a, t) => { const s = u * d, up = smooth((s - 0.1) / 0.3);   // 抬头、抬手指着天上：「看！」
      return { head: -0.34 + 0.05 * Math.sin(t * 6), lean: -0.12, eyes: 'wide', armF: [lerp(0.4, 2.55, up), lerp(0.8, 0.15, up)], armB: [0.4, 0.9],
               handF: up > 0.5 ? 'point' : 'open', handB: 'open', smile: 0.4, lift: 3 * Math.abs(Math.sin(t * 6)) }; },
    catch: (u, d, a, t) => ({ grip: 1, head: -0.18, handF: 'up', handB: 'up', eyes: 'wide', smile: 0.6, lean: -0.04, armBFront: true }),
    hug: (u, d, a, t, p) => { const s = u * d, b = Math.abs(Math.sin(t * 7.5));   // 捧着金子笑：嘴哈哈地开合，头和身子跟着笑声颠
      let hop = 0;   // 蹦：hops = [[开始, 蹦几下], ...]
      for (const [h0, n] of p.hops || []) if (s > h0 && s < h0 + n * 0.42) hop = Math.abs(Math.sin((s - h0) / 0.42 * Math.PI));
      return { grip: 1, handF: 'up', handB: 'up', happy: smooth(s / 0.15), smile: 1, laugh: smooth(s / 0.3), armBFront: true,
               lean: -0.08 + 0.06 * b, head: -0.12 + 0.12 * b, lift: 5 * b + 22 * hop }; },
    wave: (u, d, a, t) => ({ armF: [2.4, 0.5], handF: 'wave', wristF: 0.35 * Math.sin(t * 11), smile: 1, head: -0.06 }),
    cheer: (u, d, a, t) => { const hop = Math.abs(Math.sin(u * d * 5.2));
      return { armF: [2.75 + 0.15 * hop, 0.25], armB: [2.55 + 0.15 * hop, 0.35], handF: 'fist', handB: 'fist', lift: 30 * hop, eyes: 'happy', smile: 1, lean: -0.1 }; },
  };
  const FADE = { talk: 0.25, fist: 0.12, reach: 0.25, look: 0.1, crouch: 0.08, lift: 0.1, carry: 0.1, drop: 0.05, lookup: 0.3, catch: 0.45, hug: 0.15, wave: 0.2, cheer: 0.15 };
  const REST = { side: { F: [0.1, 0.3], B: [0.06, 0.3] }, q: { F: [-0.16, 0.3], B: [0.16, -0.3] } };   // 站着时手臂自然下垂（半正面时微微往两边张）

  function solve(a, t, V, view) {
    const rig = V.rig, s = rig.scale * (rig.parts.foot.size || 1), L = V.L, legLen = L.thigh + L.shin;
    const x = a.xAt(t), h = 0.05;
    const vx = (a.xAt(t + h) - a.xAt(t - h)) / (2 * h), speed = Math.abs(vx);
    const heavy = (a.actions || []).some(([t0, t1, n]) => n === 'carry' && t >= t0 && t <= t1);
    const run = heavy ? 0 : smooth((speed - 200) / 140), moving = smooth(speed / 35);
    const stride = lerp(1.25, 2.4, run) * legLen, duty = heavy ? 0.66 : lerp(0.6, 0.36, run);
    const phase = a._phase(t);
    const lean0 = moving * lerp(0.05, 0.2, run);
    const pose = {
      lean: lean0 + Math.sin(t * 2.2 + a.phase) * 0.015, head: -lean0 * 0.45 + Math.sin(t * 1.7 + a.phase) * 0.02,
      look: 1, drop: 0, lift: 0, grip: 0, reachW: 0, wristF: 0, wristB: 0,
      handF: 'open', handB: 'open', eyes: 'open', smile: 0, laugh: 0, happy: 0, strain: 0, armBFront: false,
    };
    const swing = moving * lerp(0.4, 0.85, run), elbow = lerp(0.3, 1.7, run * moving), R0 = REST[view] || REST.side;
    pose.armF = [lerp(R0.F[0], 0.1, moving) - swing * Math.cos(phase * TAU), lerp(R0.F[1], elbow, moving) + 0.2 * run * Math.sin(phase * TAU)];
    pose.armB = [lerp(R0.B[0], 0.06, moving) + swing * Math.cos(phase * TAU), lerp(R0.B[1], elbow, moving) - 0.2 * run * Math.sin(phase * TAU)];
    // 走路时手自然半握，跑步时握拳
    if (run > 0.5) { pose.handF = 'fist'; pose.handB = 'fist'; }
    for (const [t0, t1, name, p = {}] of a.actions || []) {
      const f = FADE[name] ?? 0.2, w = Math.min(smooth((t - t0) / f + 1), smooth((t1 - t) / f + 1));
      if (w <= 0) continue;
      const o = ACTIONS[name](Math.max(0, Math.min(1, (t - t0) / (t1 - t0))), t1 - t0, a, t, p, view);
      for (const [k, v] of Object.entries(o)) {
        if (typeof v === 'number' && typeof pose[k] === 'number') pose[k] = lerp(pose[k], v, w);
        else if (k.startsWith('arm')) pose[k] = [lerp(pose[k][0], v[0], w), lerp(pose[k][1], v[1], w)];
        else if (k === 'reach') pose.reach = v;
        else if (w > 0.5) pose[k] = v;
      }
    }
    // 跳：起跳前 0.18 秒下蹲蓄力，空中收腿、手往上甩，落地后 0.22 秒缓冲
    let jy = 0, tuck = 0;
    for (const [t0, t1, hgt] of a.jumps || []) {
      if (t > t0 - 0.18 && t < t0) pose.drop = Math.max(pose.drop, 0.5 * smooth((t - t0 + 0.18) / 0.18));
      if (t >= t0 && t <= t1) { const u = (t - t0) / (t1 - t0); jy = 4 * hgt * u * (1 - u); tuck = Math.sin(u * Math.PI); pose.armF[0] += 0.8 * tuck; pose.armB[0] += 0.5 * tuck; }
      if (t > t1 && t < t1 + 0.22) pose.drop = Math.max(pose.drop, 0.5 * Math.sin((t - t1) / 0.22 * Math.PI));
    }
    // 髋部高度：站着微屈膝，走/跑时屈得更多；走路一步一起伏（跑步相反：腾空时最高）
    const bob = moving * (heavy ? 0.08 : lerp(0.03, 0.07, run)) * legLen * Math.cos(2 * TAU * (phase - duty / 2)) * lerp(1, -1, run);
    const hipH = lerp(0.95, lerp(0.9, 0.84, run), moving) * legLen * (1 - 0.3 * pose.drop);
    const hipY = GROUND - rig.ankleH * s - hipH - bob - jy - pose.lift;
    return { x, vx, speed, run, moving, stride, duty, phase, pose, hipY, jy, tuck, legLen, heavy };
  }

  function draw(g, a, t) {
    const { name: view, squash } = a.viewAt(t), V = a.v[view], rig = V.rig, L = V.L;
    const st = solve(a, t, V, view), pose = st.pose, s = rig.scale * (rig.parts.foot.size || 1);
    const dirn = a.facing(t), face = dirn * Math.max(0.06, squash), toLocal = q => [(q[0] - st.x) * Math.sign(dirn), q[1]];
    const tp = rig.parts.torso;
    const torso = place(rig, 'torso', [0, st.hipY], Math.PI - pose.lean);
    const neck = torso.map(tp.neck);
    const head = place(rig, 'head', neck, Math.PI - pose.lean * 0.6 - pose.head);
    const sh = { F: torso.map(tp.shoulderF), B: torso.map(tp.shoulderB) };
    // 腿：每只脚的目标点由步态决定（着地时相对髋部匀速往后 = 相对地面不动）
    const legs = {};
    for (const [side, off] of [['F', 0], ['B', 0.5]]) {
      const hj = torso.map(tp['hip' + side]);
      const c = (((st.phase + off) % 1) + 1) % 1, half = st.duty * st.stride / 2;
      let fx, fy = 0, tilt = 0;
      if (c < st.duty) { const u = c / st.duty; fx = lerp(half, -half, u); tilt = u > 0.7 ? -0.5 * smooth((u - 0.7) / 0.3) : 0; }
      else { const u = (c - st.duty) / (1 - st.duty); fx = lerp(-half, half, smooth(u)); fy = Math.sin(u * Math.PI) * st.legLen * lerp(0.2, 0.42, st.run); tilt = lerp(-0.5, 0.25, smooth(u)); }
      fx *= st.moving; fy *= st.moving; tilt *= st.moving;
      let foot = [hj[0] + fx - (view === 'side' ? 0.04 : 0) * st.legLen, GROUND - rig.ankleH * s - fy];
      if (st.tuck) { foot = [foot[0] + (side === 'F' ? 0.2 : -0.05) * st.legLen * st.tuck, foot[1] - st.jy - st.tuck * st.legLen * 0.3]; tilt = -0.4 * st.tuck; }
      if (pose.lift) foot[1] -= pose.lift * 0.85;
      const [a1, a2] = ik(hj, foot, L.thigh, L.shin, 1);
      const th = place(rig, 'thigh', hj, a1), sn = place(rig, 'shin', th.map(rig.parts.thigh.tip), a2);
      legs[side] = { th, sn, ft: place(rig, 'foot', sn.map(rig.parts.shin.tip), tilt) };
    }
    // 手里的道具（木杆、金子）：场景给出双手要握的点（局部坐标）、画法和画在哪一层
    const held = a.hook ? a.hook(t, { x: st.x, face: Math.sign(dirn), sh, neck, head, st, toLocal, view }) : null;
    // 手臂：上臂 → 前臂 → 手；握东西时用反向运动学让手（握点）够到目标
    const arm = side => {
      const A = sh[side], fk = pose['arm' + side];
      let a1 = fk[0], a2 = fk[0] + fk[1];
      const i = side === 'F' ? 0 : 1, hn = rig.hands[pose['hand' + side]] || rig.hands.open;
      const tgt = pose.grip > 0 && held && held.grips ? [held.grips[i], pose.grip]
        : side === 'F' && pose.reachW > 0 && pose.reach ? [toLocal(pose.reach), pose.reachW] : null;
      const hA = tgt && pose.grip > 0 && held.handAngles ? held.handAngles[i] : null;
      if (tgt) {
        let ij;
        if (hA != null) {   // 手的朝向由道具决定：从握点反推手腕，前臂只够到手腕
          const w = add(tgt[0], dir(hA), -boneLen(rig, hn));
          ij = ik(A, w, L.upper, L.forearm, -1);
        } else ij = ik(A, tgt[0], L.upper, L.fore, -1);
        a1 = lerp(a1, ij[0], tgt[1]); a2 = lerp(a2, ij[1], tgt[1]);
      }
      const up = place(rig, 'upper', A, a1), fo = place(rig, 'forearm', up.map(rig.parts.upper.tip), a2);
      const hd = place(rig, hn, fo.map(rig.parts.forearm.tip), hA != null ? lerp(a2, hA, tgt[1]) : a2 + (tgt ? 0 : pose['wrist' + side]));
      return [up, fo, hd];
    };
    const armF = arm('F'), armB = arm('B');
    // 飘带：结在头上，跑得越快越往后飘，带一点抖动
    const flow = Math.min(1, st.speed / 320);
    const tails = rig.parts.tails && place(rig, 'tails', head.map(rig.parts.head.knot),
      V.tailRest - 0.5 * flow + 0.15 * (pose.lean + pose.head) + Math.sin(t * lerp(2.6, 14, flow) + a.phase) * lerp(0.11, 0.13, flow) + Math.sin(t * 1.1 + a.phase * 2) * 0.06 * (1 - flow));

    g.save(); g.translate(st.x, 0); g.scale(face, 1);
    g.fillStyle = 'rgba(60,40,20,0.32)'; g.beginPath();
    g.ellipse(0, GROUND + 4, st.legLen * 0.75 * (1 - Math.min(0.5, (st.jy + pose.lift) / 250)), 7, 0, 0, TAU); g.fill();
    const shadowOn = () => { g.shadowColor = 'rgba(50,30,10,0.26)'; g.shadowBlur = 6; g.shadowOffsetX = 3; g.shadowOffsetY = 3; };
    const put = (pl, dark) => {
      const im = (dark ? V.dark : V.img)[pl.name], p = rig.parts[pl.name];
      g.save(); g.translate(pl.at[0], pl.at[1]); g.rotate(pl.phi); g.scale(pl.s, pl.s);
      g.drawImage(im, -p.pivot[0] - V.pad, -p.pivot[1] - V.pad); g.restore();
    };
    const drawHeld = layer => { if (held && held.draw && (held.layer || 'afterHead') === layer) { g.shadowColor = 'rgba(50,30,10,0.3)'; held.draw(g); shadowOn(); } };
    shadowOn();
    if (!pose.armBFront) armB.forEach(p => put(p, true));
    put(legs.B.th, true); put(legs.B.sn, true); put(legs.B.ft, true);
    if (tails) put(tails, false);
    put(legs.F.th, false); put(legs.F.sn, false); put(legs.F.ft, false);
    put(torso, false);
    drawHeld('mid');
    const onShoulder = held && held.layer === 'shoulder';
    if (onShoulder) { put(armF[0], false); drawHeld('shoulder'); }
    g.save();   // 回头：头这张纸片绕脖子翻面
    const lk = Math.abs(pose.look) < 0.06 ? 0.06 * Math.sign(pose.look || 1) : pose.look;
    g.translate(neck[0], 0); g.scale(lk, 1); g.translate(-neck[0], 0);
    put(head, false); drawFace(g, V, head, pose, t, a);
    g.restore();
    drawHeld('afterHead');
    if (pose.armBFront) armB.forEach(p => put(p, false));   // 半正面捧东西时，远侧手臂绕到身前
    if (!onShoulder) put(armF[0], false);
    drawHeld('overUpper');
    put(armF[1], false); put(armF[2], false);
    drawHeld('front');
    if (pose.strain > 0.5) {   // 汗珠：从头顶两侧甩出去（吃力的信号）
      const top = head.map([rig.parts.head.pivot[0], rig.parts.head.pivot[1] * 0.25]);
      for (const [dx, ph] of [[-1, 0], [1, 0.5]]) {
        const u = ((t * 1.6 + ph) % 1), x = top[0] + dx * (10 + 26 * u), y = top[1] - 6 - 18 * Math.sin(u * Math.PI);
        g.save(); g.globalAlpha = Math.sin(u * Math.PI) * pose.strain; g.fillStyle = '#bfe3f2'; g.strokeStyle = '#fbf6ea'; g.lineWidth = 2;
        g.beginPath(); g.moveTo(x, y - 7); g.quadraticCurveTo(x + 5, y, x, y + 4); g.quadraticCurveTo(x - 5, y, x, y - 7); g.fill(); g.stroke(); g.restore();
      }
    }
    g.restore();
    return { x: st.x, top: head.map([rig.parts.head.pivot[0], 0])[1], st };
  }

  // 脸：眨眼、开心眯眼、睁大眼、说话的嘴型（画在头这张纸片上）
  function drawFace(g, V, head, pose, t, a) {
    const hp = V.rig.parts.head, s = head.s;
    g.save(); g.shadowColor = 'transparent';
    g.translate(head.at[0], head.at[1]); g.rotate(head.phi); g.scale(s, s); g.translate(-hp.pivot[0], -hp.pivot[1]);
    const happy = pose.eyes === 'happy' ? 1 : pose.happy, closed = Math.max(happy, a.blinkAt(t), 0.45 * pose.strain);
    for (const [ex, ey, rx, ry] of hp.eyes) {
      if (closed > 0) {
        g.fillStyle = V.skin; g.beginPath(); g.ellipse(ex, ey - ry * (1 - closed) * 0.9, rx * 1.18, ry * 1.12 * Math.max(closed, 0.15), 0, 0, TAU); g.fill();
        g.strokeStyle = '#2a1a14'; g.lineWidth = 6 / Math.max(0.5, s * 4); g.lineCap = 'round'; g.beginPath();
        if (happy > 0.5) g.arc(ex, ey + ry * 0.45, rx * 0.85, Math.PI * 1.15, Math.PI * 1.85);
        else { const y = ey + ry * (closed - 0.3); g.moveTo(ex - rx * 1.05, y - ry * 0.1); g.quadraticCurveTo(ex, y + ry * 0.25, ex + rx * 1.05, y - ry * 0.1); }
        g.stroke();
      } else if (pose.eyes === 'wide') {   // 睁大眼：眼白外一圈亮边
        g.strokeStyle = 'rgba(255,255,255,0.85)'; g.lineWidth = 3; g.beginPath(); g.ellipse(ex, ey, rx * 1.1, ry * 1.1, 0, 0, TAU); g.stroke();
      }
    }
    // 嘴：说话按音节开合；不说话时闭嘴或笑
    const [mx, my, mw] = hp.mouth, sm = pose.smile, open = Math.max(a.mouthAt(t), pose.laugh * (0.35 + 0.55 * Math.abs(Math.sin(t * 7.5))));
    g.lineCap = 'round'; g.lineJoin = 'round';
    const o = Math.max(open, sm > 0.5 ? 0.35 * sm : 0);
    if (pose.strain > 0.5 && open < 0.1) {   // 使劲：嘴紧抿、嘴角往下撇
      g.strokeStyle = '#3a1c16'; g.lineWidth = 6; g.beginPath();
      g.moveTo(mx - mw * 0.4, my + mw * 0.16); g.quadraticCurveTo(mx, my - mw * 0.14, mx + mw * 0.38, my + mw * 0.14); g.stroke();
    } else if (o > 0.06) {
      const hh = mw * (0.1 + 0.6 * o), w = mw * (0.85 + 0.35 * sm - 0.15 * open);
      g.fillStyle = '#5b1c18'; g.strokeStyle = '#3a1210'; g.lineWidth = 3;
      g.beginPath(); g.moveTo(mx - w / 2, my - hh * 0.15 * sm); g.quadraticCurveTo(mx, my - hh * 0.35 * (1 - sm), mx + w / 2, my - hh * 0.15 * sm);
      g.quadraticCurveTo(mx + w * 0.1, my + hh * 1.5, mx - w / 2, my - hh * 0.15 * sm); g.closePath(); g.fill(); g.stroke();
      g.save(); g.clip(); g.fillStyle = '#e07a70'; g.beginPath(); g.ellipse(mx, my + hh * 1.05, w * 0.3, hh * 0.45, 0, 0, TAU); g.fill();
      g.fillStyle = '#fbf6ea'; g.fillRect(mx - w / 2, my - hh * 0.5, w, hh * 0.32); g.restore();
    } else {
      g.strokeStyle = '#3a1c16'; g.lineWidth = 5; g.beginPath();
      g.moveTo(mx - mw * 0.32, my - mw * 0.04 * sm); g.quadraticCurveTo(mx, my + mw * (0.08 + 0.12 * sm), mx + mw * 0.3, my - mw * 0.06 * sm); g.stroke();
    }
    g.restore();
  }

  // ---------- 初始化 ----------
  // 一个视角的部件：先缩到画面分辨率的约 2 倍（细节够、描边粗细合适），再纸片化；远侧手脚另存一份暗一档的
  function setupView(raw, images, paperize) {
    const k = Math.min(1, raw.scale * 2.2), mul = v => Array.isArray(v) ? v.map(mul) : typeof v === 'number' ? v * k : v;
    const keep = new Set(['size']);
    const rig = { scale: raw.scale / k, ankleH: raw.ankleH * k, hands: raw.hands, parts: {} };
    for (const [n, p] of Object.entries(raw.parts)) rig.parts[n] = Object.fromEntries(Object.entries(p).map(([kk, v]) => [kk, keep.has(kk) ? v : mul(v)]));
    const V = { rig, img: {}, dark: {}, pad: 7 };
    V.L = { thigh: boneLen(rig, 'thigh'), shin: boneLen(rig, 'shin'), upper: boneLen(rig, 'upper'),
            fore: boneLen(rig, 'forearm') + boneLen(rig, rig.hands.fist), forearm: boneLen(rig, 'forearm') };   // fore = 前臂 + 手（到握点）
    for (const n of Object.keys(raw.parts)) {
      const src = images[n], c = document.createElement('canvas');
      c.width = Math.round(src.width * k); c.height = Math.round(src.height * k);
      const cg = c.getContext('2d'); cg.imageSmoothingQuality = 'high'; cg.drawImage(src, 0, 0, c.width, c.height);
      V.img[n] = paperize(c, { edge: 5, sat: 0.88, grain: 0.28 });
      const d = document.createElement('canvas'); d.width = V.img[n].width; d.height = V.img[n].height;
      const dg = d.getContext('2d'); dg.filter = 'brightness(0.86) sepia(0.12) saturate(1.1)'; dg.drawImage(V.img[n], 0, 0); V.dark[n] = d;
    }
    if (rig.parts.tails) { const p = rig.parts.tails; V.tailRest = ang(p.tip[0] - p.pivot[0], p.tip[1] - p.pivot[1]); }
    const hc = document.createElement('canvas'); hc.width = images.head.width; hc.height = images.head.height;
    const hg = hc.getContext('2d'); hg.drawImage(images.head, 0, 0);
    const [r, gg, b] = hg.getImageData(raw.parts.head.skin[0], raw.parts.head.skin[1], 1, 1).data; V.skin = `rgb(${r},${gg},${b})`;
    return V;
  }

  // views: { side: {raw, images}, q: {raw, images} }
  function setup(a, views, subtitles, paperize) {
    a.v = Object.fromEntries(Object.entries(views).map(([n, { raw, images }]) => [n, setupView(raw, images, paperize)]));
    a.phase = a.phase ?? 0;
    // 视角时间线：views: [[时刻, 'side'|'q'], ...]；换视角时 0.22 秒纸片翻面（中点换部件）
    const vt = a.views || [[0, 'side']];
    a.viewAt = t => {
      let name = vt[0][1], squash = 1;
      for (let i = 1; i < vt.length; i++) {
        const [ts, n] = vt[i], d = t - ts;
        if (Math.abs(d) < 0.11) squash = Math.min(squash, Math.abs(d) / 0.11);
        if (t >= ts) name = n;
      }
      return { name, squash: smooth(squash) };
    };
    // 眨眼：每 2.4–5.2 秒一次，0.16 秒
    const R = rand(a.seed || 7), blinks = []; for (let tt = 0.8 + R() * 2; tt < 900; tt += 2.4 + R() * 2.8) blinks.push(tt);
    a.blinkAt = t => { for (const b0 of blinks) { if (b0 > t) break; const u = (t - b0) / 0.16; if (u < 1) return Math.sin(u * Math.PI); } return 0; };
    // 嘴型：这个角色的每句台词，每个字一开一合，标点处闭嘴（接上配音后改成按音量）
    const mine = subtitles.filter(x => x[2] === a.speaker);
    a.mouthAt = t => {
      const sub = mine.find(x => t >= x[0] && t <= x[1]); if (!sub) return 0;
      const chars = [...sub[3]], per = (sub[1] - sub[0]) / chars.length, f = (t - sub[0]) / per, i = Math.floor(f);
      if (/[，。！？、…—：；,.!?]/.test(chars[i] || '')) return 0;
      return (0.5 + 0.5 * ((i * 7919) % 5) / 4) * Math.sin((f % 1) * Math.PI);
    };
    // 位置：keys 之间匀速直线，再做两遍 0.36 秒的滑动平均 → 起步、停下、变速都是平滑加减速（keys 处不会停顿）
    const n = Math.ceil((a.keys[a.keys.length - 1][0] + 2) * 60), lin = new Float64Array(n + 1);
    for (let i = 0; i <= n; i++) {
      const tt = i / 60, K = a.keys; let v = K[K.length - 1][1];
      if (tt <= K[0][0]) v = K[0][1];
      else for (let j = 1; j < K.length; j++) if (tt <= K[j][0]) { v = lerp(K[j - 1][1], K[j][1], (tt - K[j - 1][0]) / (K[j][0] - K[j - 1][0] || 1)); break; }
      lin[i] = v;
    }
    const box = (src, r) => { const out = new Float64Array(src.length); for (let i = 0; i < src.length; i++) { let sum = 0;
      for (let j = -r; j <= r; j++) sum += src[Math.max(0, Math.min(src.length - 1, i + j))]; out[i] = sum / (2 * r + 1); } return out; };
    const xs = box(box(lin, 11), 11);
    const look = (arr, t) => { const f = Math.max(0, Math.min(n, t * 60)), i = Math.floor(f); return arr[i] + (arr[Math.min(n, i + 1)] - arr[i]) * (f - i); };
    a.xAt = t => look(xs, t);
    // 步伐相位：每一小段走过的路程 ÷ 当时的步幅，累加（步幅随速度变，这样加速时脚不会倒着走）
    const L0 = a.v.side ? a.v.side.L : Object.values(a.v)[0].L, legLen = L0.thigh + L0.shin, ph = new Float64Array(n + 1);
    for (let i = 1; i <= n; i++) {
      const dx = Math.abs(xs[i] - xs[i - 1]), sp = dx * 60, run = smooth((sp - 200) / 140);
      ph[i] = ph[i - 1] + dx / (lerp(1.25, 2.4, run) * legLen);
    }
    a._phase = t => look(ph, t);
    // 脚着地的时刻（给音效用）：前脚在相位整数处着地，后脚在半数处
    a.footsteps = () => { const out = []; for (let i = 1; i <= n; i++) {
      const sp = Math.abs(xs[Math.min(n, i + 1)] - xs[Math.max(0, i - 1)]) * 30; if (sp < 25) continue;
      if (Math.floor(ph[i] * 2) !== Math.floor(ph[i - 1] * 2)) out.push([i / 60, Math.min(1, sp / 320)]); } return out; };
    // 朝向：keys 第 4 项（1 右 / -1 左），转身时纸片翻面
    a.facing = t => {
      let f = a.keys[0][3];
      for (let i = 1; i < a.keys.length; i++) { const kk = a.keys[i], p = a.keys[i - 1]; if (t < kk[0]) break;
        f = kk[3] === p[3] ? kk[3] : p[3] * Math.cos(smooth((t - kk[0]) / 0.25) * Math.PI); }
      return Math.abs(f) < 0.06 ? 0.06 * Math.sign(f || 1) : f;
    };
  }

  return { setup, draw, solve, place, ik, smooth, lerp };
})();

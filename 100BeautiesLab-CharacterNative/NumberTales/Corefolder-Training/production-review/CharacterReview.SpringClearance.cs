using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UniVRM10;

public static partial class CharacterReview
{
    [Serializable] sealed class ClearanceChain
    {
        public string chain;
        public int weightedVertices, acrossHeadMidline, leftEyeOverlapPixels, rightEyeOverlapPixels;
        public float minimumSignedLateralMM;
    }
    [Serializable] sealed class ClearancePose
    {
        public string sha256, pose;
        public int grid, leftEyePixels, rightEyePixels;
        public List<ClearanceChain> springs = new();
    }

    // Fill a 0.40 m facial square. Greater z is closer to the camera.
    // Each buffer is a single chain or an eye. Transparent texture masks and
    // intervening static hair are not part of this geometric overlap test.
    static void ClearanceTriangle(Vector3 a, Vector3 b, Vector3 c, float[] depth, int size)
    {
        float det=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
        if(Mathf.Abs(det)<1e-8f)return;
        int x0=Math.Max(0,Mathf.FloorToInt(Math.Min(a.x,Math.Min(b.x,c.x))));
        int x1=Math.Min(size-1,Mathf.CeilToInt(Math.Max(a.x,Math.Max(b.x,c.x))));
        int y0=Math.Max(0,Mathf.FloorToInt(Math.Min(a.y,Math.Min(b.y,c.y))));
        int y1=Math.Min(size-1,Mathf.CeilToInt(Math.Max(a.y,Math.Max(b.y,c.y))));
        for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++)
        {
            float dx=x+.5f-a.x, dy=y+.5f-a.y;
            float v=(dx*(c.y-a.y)-dy*(c.x-a.x))/det;
            float w=((b.x-a.x)*dy-(b.y-a.y)*dx)/det;
            if(v<0 || w<0 || v+w>1)continue;
            int p=y*size+x;
            depth[p]=Math.Max(depth[p],a.z+v*(b.z-a.z)+w*(c.z-a.z));
        }
    }

    static void SpringClearance(Vrm10Instance model, SkinnedMeshRenderer[] skins, Result stats,
                                string directory, string pose, Vector3 view)
    {
        if(!new[]{6,49,57,85}.Contains(stats.number))return;
        const int size=160;
        var animator=model.GetComponent<Animator>();
        var eyes=new[]{animator.GetBoneTransform(HumanBodyBones.LeftEye),animator.GetBoneTransform(HumanBodyBones.RightEye)};
        var center=(eyes[0].position+eyes[1].position)*.5f;
        var lateral=(eyes[0].position-eyes[1].position).normalized;
        var right=Vector3.Cross(view,Vector3.up).normalized;
        var up=Vector3.Cross(right,view).normalized;
        var chains=model.SpringBone.Springs.Select(g=>g.Joints.Select(j=>j.transform).ToArray()).ToArray();
        var data=new ClearancePose {sha256=stats.sha256,pose=pose,grid=size};
        foreach(var chain in chains)
            data.springs.Add(new ClearanceChain{chain=chain[0].name,minimumSignedLateralMM=float.MaxValue});
        var depths=Enumerable.Range(0,chains.Length+2).Select(_=>Enumerable.Repeat(float.NegativeInfinity,size*size).ToArray()).ToArray();
        var owner=new Dictionary<Transform,int>{{eyes[0],0},{eyes[1],1}};
        for(int c=0;c<chains.Length;c++)foreach(var bone in chains[c])owner[bone]=c+2;
        foreach(var skin in skins)
        {
            var slots=skin.bones.Select(b=>b && owner.TryGetValue(b,out var index) ? index : -1).ToArray();
            if(!slots.Any(s=>s>=0))continue;
            var world=Bake(skin).Select(skin.transform.TransformPoint).ToArray();
            var weights=skin.sharedMesh.boneWeights;
            var owners=new int[world.Length];
            var projected=new Vector3[world.Length];
            for(int i=0;i<world.Length;i++)
            {
                var point=world[i]-center;
                projected[i]=new Vector3((Vector3.Dot(point,right)/.4f+.5f)*size,
                                         (Vector3.Dot(point,up)/.4f+.5f)*size,Vector3.Dot(point,view));
                var w=weights[i];
                float maximum=0; int best=-1;
                void Candidate(int bone,float influence)
                {
                    if(influence<=0 || slots[bone]<0 || influence<=maximum)return;
                    best=slots[bone];maximum=influence;
                }
                Candidate(w.boneIndex0,w.weight0); Candidate(w.boneIndex1,w.weight1);
                Candidate(w.boneIndex2,w.weight2); Candidate(w.boneIndex3,w.weight3);
                owners[i]=maximum>.30f ? best : -1;
                if(owners[i]<2)continue;
                int chain=owners[i]-2;
                var rec=data.springs[chain];
                float sign=Mathf.Sign(Vector3.Dot(chains[chain][0].position-center,lateral));
                float signed=sign*Vector3.Dot(point,lateral)*1000;
                rec.weightedVertices++;
                rec.minimumSignedLateralMM=Math.Min(rec.minimumSignedLateralMM,signed);
                if(signed < -5)rec.acrossHeadMidline++;
            }
            var tris=skin.sharedMesh.triangles;
            for(int i=0;i<tris.Length;i+=3)
            {
                int a=tris[i],b=tris[i+1],c=tris[i+2],key=owners[a];
                if(key<0 || key!=owners[b] || key!=owners[c])continue;
                ClearanceTriangle(projected[a],projected[b],projected[c],depths[key],size);
            }
        }
        data.leftEyePixels=depths[0].Count(v=>!float.IsNegativeInfinity(v));
        data.rightEyePixels=depths[1].Count(v=>!float.IsNegativeInfinity(v));
        for(int chain=0;chain<chains.Length;chain++)
        {
            var rec=data.springs[chain];
            for(int i=0;i<size*size;i++)
            {
                float fur=depths[chain+2][i];
                if(!float.IsNegativeInfinity(depths[0][i]) && fur>depths[0][i]+.0005f)rec.leftEyeOverlapPixels++;
                if(!float.IsNegativeInfinity(depths[1][i]) && fur>depths[1][i]+.0005f)rec.rightEyeOverlapPixels++;
            }
            if(rec.weightedVertices==0)rec.minimumSignedLateralMM=0;
        }
        var folder=Path.Combine(directory,"spring-clearance"); Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder,pose+".json"),JsonUtility.ToJson(data,true));
    }
}

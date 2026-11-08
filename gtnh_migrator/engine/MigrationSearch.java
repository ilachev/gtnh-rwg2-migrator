package rwg2.world;

import java.io.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.biome.BiomeGenBase;
import rwg2.biomes.base.BaseBiomes;
import rwg2.biomes.realistic.RealisticBiomeBase;
import rwg2.config.ConfigRWG;
import rwg2.support.Support;
import rwg2.support.SupportBOP;
import rwg2.support.SupportTC;

/** Offline adapter for upstream RWG2 2.0.6. Never installed in the game. GPL-3.0-or-later. */
public final class MigrationSearch {
    static long seed;
    static List<int[]> samples = new ArrayList<int[]>();
    static List<Target> targets = new ArrayList<Target>();
    static Map<String, Candidate> tested = new LinkedHashMap<String, Candidate>();
    static class Target {
        int x,z; String name;
        Target(String[] p) { x=Integer.parseInt(p[0]);z=Integer.parseInt(p[1]);name=p[2]; }
    }
    static class Candidate {
        int bx,bz,lx,lz,hits;double mean,p95,max,score;int big;double[] heights;
        Candidate(int a,int b,int c,int d) { bx=a;bz=b;lx=c;lz=d; }
        String key() { return bx+","+bz+","+lx+","+lz; }
        double coverage() { return targets.isEmpty()?1.0:(double)hits/targets.size(); }
    }
    static void invoke(String name) throws Exception {
        Method method=RWGPreviewTool.class.getDeclaredMethod(name);method.setAccessible(true);method.invoke(null);
    }
    static void init(String config,int forest,int taint) throws Exception {
        ConfigRWG.init(new File(config));invoke("ensureExtendedBiomeRegistry");BaseBiomes.load();Support.init(false);
        invoke("initAddonStubs");
        // The upstream preview places stubs above 255; SupportTC scans only the first 256 IDs.
        BiomeGenBase[] registry=BiomeGenBase.getBiomeGenArray();
        for(int i=256;i<registry.length;i++) {
            BiomeGenBase biome=registry[i];if(biome==null)continue;
            int id="Magical Forest".equals(biome.biomeName)?forest:"Tainted Land".equals(biome.biomeName)?taint:-1;
            if(id<0)continue;
            if(id>=256||registry[id]!=null)throw new IllegalArgumentException("Unsupported Thaumcraft biome ID: "+id);
            Field field=BiomeGenBase.class.getDeclaredField("biomeID");field.setAccessible(true);field.setInt(biome,id);
            registry[id]=biome;registry[i]=null;
        }
        SupportBOP.init();SupportTC.init();Support.rebuildExtremeBorderMountains();
    }
    static void configure(Candidate c) {
        ConfigRWG.biomeOffsetX=c.bx;ConfigRWG.biomeOffsetZ=c.bz;
        ConfigRWG.landmassOffsetX=c.lx;ConfigRWG.landmassOffsetZ=c.lz;
    }
    static Candidate measure(Candidate c, List<int[]> points, int stride, boolean terrain) {
        configure(c);
        ChunkManagerRealistic manager=new ChunkManagerRealistic(seed,true);
        c.hits=0;
        for(Target target:targets)
            if(target.name.equalsIgnoreCase(manager.getBiomeDataAt(target.x,target.z).baseBiome.biomeName))c.hits++;
        if(!terrain){c.score=150*(1-c.coverage());return c;}
        ChunkGeneratorRealistic generator=new ChunkGeneratorRealistic(manager,seed,true);
        Map<Long,float[]> cache=new HashMap<Long,float[]>();
        RealisticBiomeBase[] biomes=new RealisticBiomeBase[256];
        double[] errors=new double[points.size()];c.heights=new double[points.size()];c.mean=0;c.max=0;c.big=0;
        for(int i=0;i<points.size();i++) {
            int[] p=points.get(i);int cx=Math.floorDiv(p[0],16),cz=Math.floorDiv(p[1],16);
            long key=((long)cx<<32)|(cz&0xffffffffL);float[] heights=cache.get(key);
            // getNewNoise reuses an internal buffer. Cache independent arrays.
            if(heights==null){heights=generator.getNewNoise(manager,cx*16,cz*16,biomes,stride).clone();cache.put(key,heights);}
            int x=Math.floorMod(p[0],16)/stride*stride,z=Math.floorMod(p[1],16)/stride*stride;
            double height=Math.max(0,Math.min(255,Math.floor(heights[x*16+z])));
            c.heights[i]=height;double error=Math.abs(height-p[2]);errors[i]=error;
            c.mean+=error;c.max=Math.max(c.max,error);if(error>24)c.big++;
        }
        Arrays.sort(errors);c.mean/=points.size();c.p95=errors[(int)Math.floor((errors.length-1)*.95)];
        c.score=c.mean+.25*c.p95+.1*c.max+12.0*c.big/points.size()+150*(1-c.coverage());
        return c;
    }
    static Candidate consider(int bx,int bz,int lx,int lz,List<int[]> points,boolean terrain) {
        Candidate c=new Candidate(bx,bz,lx,lz);Candidate old=tested.get(c.key());if(old!=null)return old;
        measure(c,points,4,terrain);c.heights=null;tested.put(c.key(),c);return c;
    }
    static List<Candidate> best(int count) {
        List<Candidate> result=new ArrayList<Candidate>(tested.values());
        Collections.sort(result,new Comparator<Candidate>() {public int compare(Candidate a,Candidate b){return Double.compare(a.score,b.score);}});
        return new ArrayList<Candidate>(result.subList(0,Math.min(count,result.size())));
    }
    static void progress(int percent,String text) {System.out.println("MIGRATION_PROGRESS\t"+percent+"\t"+text);System.out.flush();}
    static String json(Candidate c) {
        StringBuilder out=new StringBuilder();
        out.append("{\"offsets\":[").append(c.bx).append(',').append(c.bz).append(',').append(c.lx).append(',').append(c.lz);
        out.append("],\"mean\":").append(c.mean).append(",\"p95\":").append(c.p95).append(",\"max\":").append(c.max);
        out.append(",\"over24\":").append(c.big).append(",\"score\":").append(c.score);
        out.append(",\"biome_hits\":").append(c.hits).append(",\"biome_samples\":").append(targets.size());
        out.append(",\"coverage\":").append(c.coverage()).append(",\"heights\":[");
        for(int i=0;i<c.heights.length;i++){if(i>0)out.append(',');out.append(c.heights[i]);}
        return out.append("]}").toString();
    }
    public static void main(String[] args) throws Exception {
        if(args.length!=10)throw new IllegalArgumentException("config seed survey targets output radius step forestId taintId mode");
        seed=Long.parseLong(args[1]);init(args[0],Integer.parseInt(args[7]),Integer.parseInt(args[8]));
        for(String line:Files.readAllLines(Paths.get(args[2]),StandardCharsets.UTF_8)) {
            if(line.trim().isEmpty())continue;String[] p=line.split("\t");
            samples.add(new int[]{Integer.parseInt(p[0]),Integer.parseInt(p[1]),Integer.parseInt(p[2])});
        }
        for(String line:Files.readAllLines(Paths.get(args[3]),StandardCharsets.UTF_8))
            if(!line.trim().isEmpty())targets.add(new Target(line.split("\t",3)));
        if(samples.isEmpty())throw new IllegalArgumentException("Empty boundary survey");
        Set<String> available=new TreeSet<String>(String.CASE_INSENSITIVE_ORDER);
        for(RealisticBiomeBase biome:new ChunkManagerRealistic(seed,true).getConfiguredBiomes())
            if(biome!=null)available.add(biome.baseBiome.biomeName);
        for(Target target:targets)if(!available.contains(target.name))throw new IllegalArgumentException("Unknown RWG2 biome: "+target.name+". Available: "+available);
        List<int[]> coarse=new ArrayList<int[]>();
        int count=Math.min(64,samples.size());for(int i=0;i<count;i++)coarse.add(samples.get(i*samples.size()/count));
        Candidate baseline=measure(new Candidate(0,0,0,0),samples,1,true);
        if(args[9].startsWith("evaluate:")) {
            String[] p=args[9].substring(9).split(",");
            if(p.length!=4)throw new IllegalArgumentException("Four offsets required");
            Candidate c=measure(new Candidate(Integer.parseInt(p[0]),Integer.parseInt(p[1]),Integer.parseInt(p[2]),Integer.parseInt(p[3])),samples,1,true);
            Files.write(Paths.get(args[4]),("{\"baseline\":"+json(baseline)+",\"candidates\":["+json(c)+"]}").getBytes(StandardCharsets.UTF_8));return;
        }
        int radius=Integer.parseInt(args[5]),step=Integer.parseInt(args[6]);
        if(radius<0||radius>16384||step<32||step>2048)throw new IllegalArgumentException("Search bounds out of range");
        progress(5,"Searching biome placements");
        boolean direct=targets.isEmpty();
        for(int x=-radius;x<=radius;x+=step) {
            for(int z=-radius;z<=radius;z+=step)consider(x,z,0,0,coarse,direct);
            progress(5+(int)(35.0*(x+radius)/Math.max(1,2*radius)),"Searching biome placements");
        }
        for(Candidate c:best(12))for(int x=c.bx-step;x<=c.bx+step;x+=Math.max(32,step/4))
            for(int z=c.bz-step;z<=c.bz+step;z+=Math.max(32,step/4))consider(x,z,0,0,coarse,direct);
        progress(45,"Comparing boundary terrain");
        List<Candidate> candidates=best(direct?100:1000);
        if(!direct && candidates.get(0).hits==0)throw new IllegalArgumentException("No requested biome found. Broaden the search or choose another biome.");
        for(Candidate c:candidates){measure(c,coarse,4,true);c.heights=null;}
        // Discard biome-only probes before terrain ranking.
        tested.clear();for(Candidate c:candidates)tested.put(c.key(),c);
        for(Candidate c:best(3))for(int x=-4096;x<=4096;x+=1024)
            for(int z=-4096;z<=4096;z+=1024)consider(c.bx,c.bz,x,z,coarse,true);
        progress(65,"Refining selected placements");
        for(Candidate c:best(8))for(int x=c.bx-64;x<=c.bx+64;x+=32)
            for(int z=c.bz-64;z<=c.bz+64;z+=32)consider(x,z,c.lx,c.lz,coarse,true);
        List<Candidate> exact=best(32);int done=0;
        for(Candidate c:exact){measure(c,samples,1,true);progress(70+25*(++done)/exact.size(),"Checking full boundary samples");}
        Collections.sort(exact,new Comparator<Candidate>() {public int compare(Candidate a,Candidate b){return Double.compare(a.score,b.score);}});
        StringBuilder out=new StringBuilder("{\"baseline\":"+json(baseline)+",\"candidates\":[");
        for(int i=0;i<Math.min(10,exact.size());i++){if(i>0)out.append(',');out.append(json(exact.get(i)));}
        out.append("]}");Files.write(Paths.get(args[4]),out.toString().getBytes(StandardCharsets.UTF_8));progress(100,"Search complete");
    }
}
